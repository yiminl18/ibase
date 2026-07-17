"""Command-line interface for ibase.

Usage:
    ibase add <url-or-path> [--note NOTE] [--topic T ...]
    ibase list [--read | --unread] [--topic T] [--sort FIELD] [--q QUERY]
    ibase serve [--host HOST] [--port PORT]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import config
from .ingest.digest import digest
from .llm.engine import LLMEngine
from .query.pipeline import run_query
from .store import Store


def _cmd_add(args) -> int:
    config.ensure_dirs()
    store = Store()
    llm = LLMEngine()
    if not llm.available():
        print("note: LLM unavailable — item stored without a summary.",
              file=sys.stderr)
    item = digest(args.source, store, llm=llm, note=args.note or "",
                  topics=args.topic or [])
    print(f"[{item.id}] {item.name}  ({item.format}, {item.fetch_status})")
    if item.summary:
        print(f"  summary: {item.summary}")
    if item.topics:
        print(f"  topics : {', '.join(item.topics)}")
    return 0


def _cmd_list(args) -> int:
    store = Store()
    read: Optional[bool] = None
    if args.read:
        read = True
    elif args.unread:
        read = False
    items = run_query(
        store.list_items(),
        read=read,
        topic=args.topic,
        q=args.q or "",
        q_mode="auto",
        sort=args.sort,
        order=args.order,
        llm=LLMEngine(),
    )
    if not items:
        print("(no items)")
        return 0
    for it in items:
        mark = "✓" if it.read else " "
        topics = f" [{', '.join(it.topics)}]" if it.topics else ""
        print(f"[{mark}] {it.id}  {it.name}{topics}")
        if it.summary:
            print(f"       {it.summary}")
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    config.ensure_dirs()
    print(f"ibase serving at http://{args.host}:{args.port}")
    uvicorn.run("ibase.main:app", host=args.host, port=args.port,
                reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ibase",
                                     description="Personal data management system.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="digest a URL or local file")
    p_add.add_argument("source", help="a URL or local file path")
    p_add.add_argument("--note", default="")
    p_add.add_argument("--topic", action="append", help="repeatable, up to 3")
    p_add.set_defaults(func=_cmd_add)

    p_list = sub.add_parser("list", help="list stored items")
    g = p_list.add_mutually_exclusive_group()
    g.add_argument("--read", action="store_true")
    g.add_argument("--unread", action="store_true")
    p_list.add_argument("--topic")
    p_list.add_argument("--q", help="search query")
    p_list.add_argument("--sort", default="inserted_at")
    p_list.add_argument("--order", default="desc", choices=["asc", "desc"])
    p_list.set_defaults(func=_cmd_list)

    p_serve = sub.add_parser("serve", help="launch the web app")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
