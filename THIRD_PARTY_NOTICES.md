# Third-party material

`data/upstream/` preserves benchmark, schema, manifest and experiment configuration
from [TwoSpoon/READ](https://github.com/twospoon/READ), commit
`c3c368d4a78b0a152f0dfe7f9f74110347f02397`.

Copyright © 2026 Sagar Tamang, Ayush Vyas, Tabarakul Hazarika (TwoSpoon).
These files are MIT-licensed by the upstream project. Their complete license is
preserved at [data/upstream/LICENSE](data/upstream/LICENSE).
Git blob SHA-1 and SHA-256 digests are in `data/upstream/manifest.json`.
The two large result logs are downloaded on demand by `fetch-upstream` at the same
commit and verified byte for byte; they are not duplicated in this repository.

Our reports derive from those records and retain attribution. Their responses and
judge outputs were produced by the authors, not by a new execution here. The source
government PDF/Markdown is not redistributed. The original document has its own terms.

The independent `read_vs_rag/` implementation is not the official READ package and
is not endorsed by TwoSpoon. The line tools implement the same family of operations
using a local function-calling adapter, not the authors' MCP transport.

Optional BGE embedding/reranking models are downloaded by their own libraries under
their published model licenses. No model weights are bundled.
