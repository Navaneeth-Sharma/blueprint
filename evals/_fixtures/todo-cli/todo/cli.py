"""todo add <title> | todo list | todo done <id>"""
import argparse
import sys

from . import store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="todo")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("title")
    sub.add_parser("list")
    sub.add_parser("done").add_argument("id", type=int)
    args = parser.parse_args(argv)

    items = store.load()
    if args.cmd == "add":
        next_id = max((i["id"] for i in items), default=0) + 1
        items.append({"id": next_id, "title": args.title, "done": False})
        store.save(items)
        print(next_id)
    elif args.cmd == "done":
        for item in items:
            if item["id"] == args.id:
                item["done"] = True
                store.save(items)
                break
        else:
            print(f"no todo {args.id}", file=sys.stderr)
            return 1
    else:
        for item in items:
            mark = "x" if item["done"] else " "
            print(f"{item['id']:>3}  [{mark}]  {item['title']}")
    return 0
