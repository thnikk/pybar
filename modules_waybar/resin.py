#!/usr/bin/python3 -u
"""
Description: Genshin resin module
Author: thnikk
"""
import asyncio
import json
from datetime import datetime, timezone
import os
import genshin


def time_diff(now, future, rate):
    """ Calculate time difference and return string """
    max_time = future - now
    until_next = (max_time.seconds // 60) % (rate * 40)
    return f"{until_next // 60}:{until_next % 60}"


async def generate_cache(config):
    """ Main function """
    # Get current time
    time_now = datetime.now(timezone.utc)

    try:
        # pylint: disable=no-member
        genshin_client = genshin.Client({
            "ltuid": config["ltuid"],
            "ltoken": config["ltoken"]})
        genshin_notes = await genshin_client.get_notes()
        genshin_user = await genshin_client.get_full_genshin_user(
                config["uid"])
        com_prog = genshin_notes.completed_commissions + \
            int(genshin_notes.claimed_commission_reward)
        cache = {
            "Name": "Genshin Impact",
            "Icon": "",
            "Resin": genshin_notes.current_resin,
            "Until next 40": time_diff(
                time_now, genshin_notes.resin_recovery_time, 8),
            "Dailies completed": f"{com_prog}/5",
            "Remaining boss discounts":
            genshin_notes.remaining_resin_discounts,
            "Realm currency": genshin_notes.current_realm_currency,
            "Abyss progress": genshin_user.abyss.current.max_floor,
            "Abyss stars": genshin_user.abyss.current.total_stars,
            "timestamp": datetime.timestamp(time_now)
        }
    except genshin.errors.GenshinException:
        return None
    return cache


def genshin_module(cache):
    """ Generate waybar output for Genshin """
    output = {}
    dailies = cache["Dailies completed"].split("/")
    dailies_completed = int(dailies[0]) == int(dailies[1])
    realm_currency_capped = cache['Realm currency'] >= 2000

    if not dailies_completed and not realm_currency_capped:
        output['class'] = 'red'
    if dailies_completed and realm_currency_capped:
        output['class'] = 'yellow'
    if not dailies_completed and realm_currency_capped:
        output['class'] = 'orange'

    output['text'] = f"{cache['Icon']} {cache['Resin']}"

    output['tooltip'] = cache['timestamp']

    output['widget'] = cache
    return output


def module(module_config):
    """ Module """
    cache = asyncio.run(generate_cache(module_config))
    output = genshin_module(cache)
    return output


def main():
    """ Main function """
    with open(
        os.path.expanduser('~/.config/pybar-testing/config.json'),
        'r', encoding='utf-8'
    ) as file:
        config = json.loads(file.read())['modules']['resin']
    print(json.dumps(module(config), indent=4))


if __name__ == "__main__":
    main()
