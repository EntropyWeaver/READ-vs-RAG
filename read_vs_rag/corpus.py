"""Line-addressed Markdown. All tools return original text with stable coordinates."""

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .io import sha256_file, stable_hash


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("\u00ad", "")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    spaced = " ".join(re.sub(r"[^\w.]", " ", text).split())
    squashed = re.sub(r"[^\w.]", "", text)
    return spaced, squashed


@dataclass(frozen=True)
class Line:
    doc: str
    line: int
    text: str

    def as_dict(self):
        return {"doc": self.doc, "line": self.line, "text": self.text}


class Corpus:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.docs, self.hashes = {}, {}
        for p in sorted(self.root.rglob("*.md")):
            if not p.resolve().is_relative_to(self.root):
                raise ValueError(f"Corpus symlink escapes root: {p.name}")
            name = p.relative_to(self.root).as_posix()
            if len(name) > 200:
                raise ValueError("Document IDs must be at most 200 characters")
            self.docs[name] = p.read_text(encoding="utf-8").splitlines()
            self.hashes[name] = sha256_file(p)
        if not self.docs:
            raise ValueError(f"No Markdown documents in {self.root}")
        self.fingerprint = stable_hash(self.hashes)

    def lines(self, doc, start, end):
        if doc not in self.docs:
            raise ValueError("Unknown document ID; use memory_list")
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(self.docs[doc]):
            raise ValueError("Invalid 1-based inclusive line range")
        return [Line(doc, n, self.docs[doc][n - 1]) for n in range(start, end + 1)]

    def all_lines(self):
        return [Line(doc, i, text) for doc, lines in self.docs.items() for i, text in enumerate(lines, 1)]


def bounded_result(lines, max_chars, **metadata):
    entries = []
    response = {**metadata, "entries": entries, "truncated": False}
    # Never claim exposure to a line whose text was omitted or cut.
    for line in lines:
        entries.append(line.as_dict())
        if len(json.dumps(response, ensure_ascii=False)) > max_chars - 30:
            entries.pop()
            response["truncated"] = True
            break
    return response


class ReadTools:
    def __init__(self, corpus, *, normalized=True, outline=True, max_lines=400, max_chars=24000):
        self.corpus, self.normalized, self.outline_enabled = corpus, normalized, outline
        self.max_lines, self.max_chars = max_lines, max_chars

    def call(self, name, args):
        if name == "memory_list":
            # Paginate metadata, avoiding an unbounded file listing on large corpora.
            offset = int(args.get("offset", 0))
            if offset < 0:
                raise ValueError("offset must be nonnegative")
            items = list(self.corpus.docs.items())
            docs = [{"doc": d, "lines": len(ls)} for d, ls in items[offset:offset + 30]]
            return {"documents": docs, "next_offset": offset + 30 if offset + 30 < len(items) else None,
                    "entries": []}
        doc = args.get("doc")
        if doc is not None and doc not in self.corpus.docs:
            raise ValueError("Unknown document ID")
        if name == "memory_read":
            start, end = args["start"], args["end"]
            if type(start) is not int or type(end) is not int or end - start + 1 > self.max_lines:
                raise ValueError(f"memory_read allows at most {self.max_lines} whole lines")
            return bounded_result(self.corpus.lines(doc, start, end), self.max_chars)
        if name == "memory_outline" and self.outline_enabled:
            offset = int(args.get("offset", 0))
            if offset < 0:
                raise ValueError("offset must be nonnegative")
            lines = [line for line in self.corpus.all_lines() if (doc is None or line.doc == doc)
                     and re.match(r"^\s{0,3}#{1,6}\s+", line.text)]
            result = bounded_result(lines[offset:offset + 100], self.max_chars, total_headings=len(lines))
            count = len(result["entries"])
            result["next_offset"] = offset + count if count and offset + count < len(lines) else None
            return result
        if name == "memory_grep":
            query = args["query"]
            if not isinstance(query, str) or not query.strip() or len(query) > 500:
                raise ValueError("query must contain 1–500 characters")
            offset = int(args.get("offset", 0))
            if offset < 0:
                raise ValueError("offset must be nonnegative")
            spaced, squashed = normalize(query)
            if self.normalized and not squashed:
                raise ValueError("query is empty after normalization")
            hits = []
            for line in self.corpus.all_lines():
                if doc is not None and line.doc != doc:
                    continue
                a, b = normalize(line.text) if self.normalized else ("", "")
                match = (spaced in a or squashed in b) if self.normalized else query.casefold() in line.text.casefold()
                if match:
                    hits.append(line)
            result = bounded_result(hits[offset:offset + 40], self.max_chars, total_matches=len(hits))
            count = len(result["entries"])
            result["next_offset"] = offset + count if count and offset + count < len(hits) else None
            return result
        raise ValueError(f"Tool unavailable: {name}")

    def declarations(self):
        string = {"type": "STRING"}
        integer = {"type": "INTEGER"}
        def tool(name, desc, props, required=()):
            return {"name": name, "description": desc,
                    "parameters": {"type": "OBJECT", "properties": props, "required": list(required)}}
        result = [
            tool("memory_list", "List document IDs and line counts; paginate with offset.", {"offset": integer}),
            tool("memory_grep", "Literal lexical search; returns original matching lines. Use short terms; "
                 "this is not semantic search. Paginate with offset.",
                 {"query": string, "doc": string, "offset": integer}, ["query"]),
            tool("memory_read", f"Read original lines including nearby units, column headers and years; "
                 f"1-based inclusive, maximum {self.max_lines} lines.",
                 {"doc": string, "start": integer, "end": integer}, ["doc", "start", "end"]),
        ]
        if self.outline_enabled:
            result.append(tool("memory_outline", "List Markdown headings with line coordinates; paginate with offset.",
                               {"doc": string, "offset": integer}))
        return result
