window.DEBUGGER_CASES = [
  {
    "id": "total",
    "question_id": "lookup-016",
    "outputs": [
      {
        "system": "read",
        "answer": "The total Revenue Expenditure for 2024-25 was ₹ 1,48,743.95 crore.",
        "abstained": false,
        "correct": false,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 5845,
            "end": 5848
          }
        ],
        "seconds": 102.44,
        "usd": 0.01107,
        "steps": [
          {
            "tool": "memory_list",
            "args": {
              "offset": 0
            },
            "seconds": 0.0,
            "returned": 0,
            "total_matches": null,
            "truncated": false,
            "documents": [
              {
                "doc": "gujarat-vol-i.md",
                "lines": 7226
              }
            ],
            "preview": []
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "Revenue Expenditure",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.199,
            "returned": 24,
            "total_matches": 24,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 5845,
                "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 5858,
              "end": 5872
            },
            "seconds": 0.0,
            "returned": 15,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 5860,
                "text": "advances given by the State Government) was reconciled."
              }
            ]
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "2024-25",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.091,
            "returned": 40,
            "total_matches": 85,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 224,
                "text": "disbursements of the Government of Gujarat for the year 2024-25"
              }
            ]
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "Revenue Expenditure of ₹",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.047,
            "returned": 4,
            "total_matches": 4,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 5845,
                "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 5839,
              "end": 5847
            },
            "seconds": 0.0,
            "returned": 9,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 5845,
                "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 5845,
              "end": 5850
            },
            "seconds": 0.0,
            "returned": 6,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 5845,
                "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
              },
              {
                "line": 5848,
                "text": "₹ 1,99,611.44 crore) and Capital Expenditure of ₹ 45,112.87 crore (68.95 _per cent_ of total"
              }
            ]
          }
        ]
      },
      {
        "system": "bm25",
        "answer": "The total Revenue Expenditure for 2024-25 was ₹ 1,99,611.44 crore.",
        "abstained": false,
        "correct": true,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 5845,
            "end": 5848
          }
        ],
        "seconds": 17.62,
        "usd": 0.009222,
        "steps": [
          {
            "tool": "rag",
            "args": {
              "query": "What was the total Revenue Expenditure for 2024-25?"
            },
            "seconds": 0.03,
            "returned": 376,
            "total_matches": null,
            "truncated": true,
            "documents": [],
            "preview": [
              {
                "line": 5845,
                "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
              },
              {
                "line": 5848,
                "text": "₹ 1,99,611.44 crore) and Capital Expenditure of ₹ 45,112.87 crore (68.95 _per cent_ of total"
              }
            ]
          }
        ]
      }
    ],
    "evidence": [
      {
        "line": 5845,
        "text": "Revenue Expenditure of ₹ 1,48,743.95 crore (74.52 _per cent_ of total Revenue Expenditure"
      },
      {
        "line": 5846,
        "text": ""
      },
      {
        "line": 5847,
        "text": ""
      },
      {
        "line": 5848,
        "text": "₹ 1,99,611.44 crore) and Capital Expenditure of ₹ 45,112.87 crore (68.95 _per cent_ of total"
      }
    ]
  },
  {
    "id": "consolidated",
    "question_id": "agg-020",
    "outputs": [
      {
        "system": "read",
        "answer": "In 2024-25, Consolidated Fund expenditure was 2,97,717.24 crore: Revenue 1,99,611.44 crore, Capital 65,428.32 crore, and Loans 32,677.48 crore.",
        "abstained": false,
        "correct": true,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 2183,
            "end": 2186
          },
          {
            "doc": "gujarat-vol-i.md",
            "start": 2259,
            "end": 2265
          }
        ],
        "seconds": 89.77,
        "usd": 0.008774,
        "steps": [
          {
            "tool": "memory_list",
            "args": {
              "offset": 0
            },
            "seconds": 0.0,
            "returned": 0,
            "total_matches": null,
            "truncated": false,
            "documents": [
              {
                "doc": "gujarat-vol-i.md",
                "lines": 7226
              }
            ],
            "preview": []
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "Consolidated Fund expenditure",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.064,
            "returned": 0,
            "total_matches": 0,
            "truncated": false,
            "documents": [],
            "preview": []
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "Consolidated Fund",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.267,
            "returned": 40,
            "total_matches": 43,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 2259,
                "text": "**Total Consolidated Fund**"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 2245,
              "end": 2275
            },
            "seconds": 0.002,
            "returned": 31,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 2259,
                "text": "**Total Consolidated Fund**"
              },
              {
                "line": 2261,
                "text": "**Expenditure**"
              },
              {
                "line": 2265,
                "text": "**1,99,611.44** **65,428.32** **32,677.48** **2,97,717.24**"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 2170,
              "end": 2266
            },
            "seconds": 0.004,
            "returned": 97,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 2183,
                "text": "**(₹ in crore)**"
              },
              {
                "line": 2186,
                "text": "**Description** **Revenue** **Capital** **Loans and** **Total**"
              },
              {
                "line": 2259,
                "text": "**Total Consolidated Fund**"
              }
            ]
          }
        ]
      },
      {
        "system": "hybrid_rrf",
        "answer": "The Consolidated Fund expenditure in 2024-25 was ₹4,647.19 crore, split as Revenue ₹1,296.32 crore, Capital ₹3,108.05 crore, and Loans ₹242.82 crore.",
        "abstained": false,
        "correct": false,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 5735,
            "end": 5741
          }
        ],
        "seconds": 19.14,
        "usd": 0.012341,
        "steps": [
          {
            "tool": "rag",
            "args": {
              "query": "What was the total Consolidated Fund expenditure in 2024-25, and how did it split between Revenue, Capital, and Loans?"
            },
            "seconds": 0.183,
            "returned": 408,
            "total_matches": null,
            "truncated": true,
            "documents": [],
            "preview": [
              {
                "line": 5735,
                "text": "provisions under these heads and incurred ₹ 1,296.32 crore under the 72 Sub Heads in Revenue"
              },
              {
                "line": 5738,
                "text": "Section and ₹ 3,108.05 crore under the 59 Sub Heads in Capital Section and ₹ 242.82 crore"
              },
              {
                "line": 5741,
                "text": "under the 03 Sub Heads in Loan Section during the year 2024-25."
              }
            ]
          }
        ]
      }
    ],
    "evidence": [
      {
        "line": 2109,
        "text": "**Description** **Revenue** **Capital** **Loans and** **Total**"
      },
      {
        "line": 2259,
        "text": "**Total Consolidated Fund**"
      },
      {
        "line": 2261,
        "text": "**Expenditure**"
      },
      {
        "line": 2265,
        "text": "**1,99,611.44** **65,428.32** **32,677.48** **2,97,717.24**"
      }
    ]
  },
  {
    "id": "scope",
    "question_id": "unans-002",
    "outputs": [
      {
        "system": "read",
        "answer": "Maharashtra's revenue surplus in 2024-25 was 33,477.03 crore.",
        "abstained": false,
        "correct": false,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 1073,
            "end": 1073
          }
        ],
        "seconds": 91.15,
        "usd": 0.01093,
        "steps": [
          {
            "tool": "memory_list",
            "args": {
              "offset": 0
            },
            "seconds": 0.0,
            "returned": 0,
            "total_matches": null,
            "truncated": false,
            "documents": [
              {
                "doc": "gujarat-vol-i.md",
                "lines": 7226
              }
            ],
            "preview": []
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "Maharashtra",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.099,
            "returned": 1,
            "total_matches": 1,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 4751,
                "text": "to the end of 2024-25 to Gujarat by the Accountant General, Maharashtra under Bombay Reorganisation"
              }
            ]
          },
          {
            "tool": "memory_grep",
            "args": {
              "query": "revenue surplus",
              "doc": "gujarat-vol-i.md",
              "offset": 0
            },
            "seconds": 0.109,
            "returned": 5,
            "total_matches": 5,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 1073,
                "text": "**Revenue Deficit** Nil Nil **Revenue Surplus** 18,942.94 33,477.03"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 4748,
              "end": 4766
            },
            "seconds": 0.0,
            "returned": 19,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 4750,
                "text": "I. Net effect of Balance under Dept, Deposit and Remittance heads of the composite Bombay State allocated"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 1058,
              "end": 1078
            },
            "seconds": 0.0,
            "returned": 21,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 1073,
                "text": "**Revenue Deficit** Nil Nil **Revenue Surplus** 18,942.94 33,477.03"
              }
            ]
          },
          {
            "tool": "memory_read",
            "args": {
              "doc": "gujarat-vol-i.md",
              "start": 1000,
              "end": 1074
            },
            "seconds": 0.003,
            "returned": 75,
            "total_matches": null,
            "truncated": false,
            "documents": [],
            "preview": [
              {
                "line": 1073,
                "text": "**Revenue Deficit** Nil Nil **Revenue Surplus** 18,942.94 33,477.03"
              }
            ]
          }
        ]
      },
      {
        "system": "hybrid_rrf",
        "answer": "Abstain: the supplied evidence is from Gujarat’s Finance Accounts and does not support Maharashtra’s 2024-25 revenue surplus.",
        "abstained": true,
        "correct": true,
        "citations": [
          {
            "doc": "gujarat-vol-i.md",
            "start": 2,
            "end": 3
          },
          {
            "doc": "gujarat-vol-i.md",
            "start": 1073,
            "end": 1074
          },
          {
            "doc": "gujarat-vol-i.md",
            "start": 4718,
            "end": 4719
          }
        ],
        "seconds": 12.37,
        "usd": 0.009036,
        "steps": [
          {
            "tool": "rag",
            "args": {
              "query": "According to this volume, what was the state of Maharashtra's revenue surplus in 2024-25?"
            },
            "seconds": 0.097,
            "returned": 361,
            "total_matches": null,
            "truncated": true,
            "documents": [],
            "preview": [
              {
                "line": 3,
                "text": "## **Volume‐I** **2024‐2025** **Government of Gujarat**"
              },
              {
                "line": 4718,
                "text": "**Total: Provision of Funds** **3,91,899.23(#)** **48,964.89** **4,40,864.11(B)**"
              },
              {
                "line": 4719,
                "text": "Deduct: Revenue Deficit/ Add:Revenue Surplus 18,942.94"
              }
            ]
          }
        ]
      }
    ],
    "evidence": [
      {
        "line": 1,
        "text": "# **Finance Accounts**"
      },
      {
        "line": 3,
        "text": "## **Volume‐I** **2024‐2025** **Government of Gujarat**"
      },
      {
        "line": 949,
        "text": "**STATEMENT No. 2 - STATEMENT OF RECEIPTS AND DISBURSEMENTS**"
      },
      {
        "line": 953,
        "text": "**2024-25** **2023-24** **2024-25** **2023-24**"
      },
      {
        "line": 1073,
        "text": "**Revenue Deficit** Nil Nil **Revenue Surplus** 18,942.94 33,477.03"
      }
    ]
  }
];
