#!/usr/bin/python3
import json
try:
    from transmission_rpc import Client
except ModuleNotFoundError:
    print(
        'Missing optional dependency for '
        'transmission module: [pip] transmission-rpc')


def module(config):
    """ Module """
    try:
        c = Client(
            host=config["host"] if "host" in config else "localhost",
            port=config["port"] if "port" in config else 9091
        )
    # Return nothing if transmission library is missing
    except NameError:
        return {"text": ""}

    torrents = c.get_torrents()
    downloads = 0
    uploads = 0
    for torrent in torrents:
        if torrent.status == 'downloading':
            downloads += 1
        if torrent.status == 'seeding':
            uploads += 1

    n = []
    if downloads:
        n.append(f" {downloads}")
    if uploads:
        n.append(f" {uploads}")
    text = "  ".join(n)
    return {"text": text}


def main():
    """ Main function """
    print(json.dumps(module({}), indent=4))


if __name__ == "__main__":
    main()
