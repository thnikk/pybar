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
    downloading = []
    uploading = []
    for torrent in torrents:
        if torrent.status == 'downloading':
            downloads += 1
            downloading.append(f'{torrent.name} {int(torrent.progress)}%')
        if torrent.status == 'seeding':
            uploads += 1
            uploading.append(torrent.name)

    n = []
    if downloads:
        n.append(f" {downloads}")
    if uploads:
        n.append(f" {uploads}")
    text = "  ".join(n)

    m = []
    if downloading:
        section = []
        section.append('Downloading:')
        for name in downloading:
            section.append(name)
        if section:
            m.append('\n'.join(section))

    if uploading:
        section = []
        section.append('Uploading:')
        for name in uploading:
            section.append(name)
        if section:
            m.append('\n'.join(section))

    tooltip = "\n\n".join(m) if m else ""

    return {"text": text, "tooltip": tooltip}


def main():
    """ Main function """
    print(json.dumps(module({}), indent=4))


if __name__ == "__main__":
    main()
