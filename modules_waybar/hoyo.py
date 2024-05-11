#!/usr/bin/python3 -u
""" Show stats for Genshin and HSR in waybar module """
import asyncio
import json
from datetime import datetime, timezone
import os
import time
import configparser
import argparse
from modules_waybar.common import print_debug
import modules_waybar.tooltip as tt
import genshin

cache_file = os.path.expanduser("~/.cache/hoyo-stats.json")
config_file = os.path.expanduser("~/.config/hoyo-stats.ini")


def get_args():
    """ Get arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g', '--game', default='genshin', help='Game to get info for')
    args = parser.parse_args()
    return args


def get_config():
    """ Get or create config file """
    # Create config file if it doesn't exist
    if not os.path.exists(config_file):
        with open(config_file, "a", encoding='utf-8') as f:
            f.write("[settings]\nltuid = \nltoken = \ngenshin_id = ")
            f.close()
    # Load config from cache
    config = configparser.ConfigParser()
    config.read(config_file)
    return config


def config_fail():
    """ Print info to waybar on fail """
    print(json.dumps({"text": ("Set up hoyo module in "
                               "~/.config/hoyo-stats.ini")}))


def time_diff(now, future, rate):
    """ Calculate time difference and return string """
    max_time = future - now
    until_next = (max_time.seconds // 60) % (rate * 40)
    return f"{until_next // 60}:{until_next % 60}"


def old(old_time, min_diff):
    """ Check age of datetime objects """
    diff = (datetime.now() - old_time).total_seconds()
    if diff > 60*min_diff:
        # print_debug('Cache is old, fetching new data.')
        return True
    return False


# pylint: disable=too-many-locals
async def generate_cache(config, game):
    """ Main function """
    cookies = {
            "ltuid": config["settings"]["ltuid"],
            "ltoken": config["settings"]["ltoken"]
            }
    # Get current time
    time_now = datetime.now(timezone.utc)

    for x in range(0, 3):  # pylint: disable=unused-variable
        try:
            with open(cache_file, encoding='utf-8') as json_file:
                cache = json.load(json_file)
                break
        except json.decoder.JSONDecodeError:
            # print_debug(
            #     "Couldn't decode json cache, waiting and trying again.")
            time.sleep(3)
        except FileNotFoundError:
            cache = {}

    try:
        if game == 'genshin':
            try:
                if old(
                    datetime.fromtimestamp(cache['genshin']['timestamp']), 5
                ):
                    raise ValueError
            except (KeyError, ValueError):
                # pylint: disable=no-member
                genshin_client = genshin.Client(cookies)
                genshin_notes = await genshin_client.get_notes()
                genshin_user = await genshin_client.get_full_genshin_user(
                        config["settings"]["genshin_id"])
                com_prog = genshin_notes.completed_commissions + \
                    int(genshin_notes.claimed_commission_reward)
                cache['genshin'] = {
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

        if game == 'hsr':
            try:
                if old(
                    datetime.fromtimestamp(cache['hsr']['timestamp']), 5
                ):
                    raise ValueError
            except (KeyError, ValueError):
                # pylint: disable=no-member
                hsr_client = genshin.Client(
                    cookies, game=genshin.Game.STARRAIL)
                hsr_notes = await hsr_client.get_starrail_notes()
                hsr_user = await hsr_client.get_starrail_challenge(
                        config["settings"]["hsr_id"])
                moc_floors = [floor.name for floor in hsr_user.floors]
                daily_prog = hsr_notes.current_train_score // 100
                cache["hsr"] = {
                    "Name": "Honkai Star Rail",
                    "Icon": "",
                    "Resin": hsr_notes.current_stamina,
                    "Until next 40":
                    time_diff(time_now, hsr_notes.stamina_recovery_time, 6),
                    "Dailies completed": f"{daily_prog}/5",
                    "Remaining boss discounts":
                    hsr_notes.remaining_weekly_discounts,
                    "SU weekly score":
                    f"{hsr_notes.current_rogue_score}/"
                    f"{hsr_notes.max_rogue_score}",
                    "Abyss progress": len(moc_floors),
                    "Abyss stars": hsr_user.total_stars,
                    "timestamp": datetime.timestamp(time_now)
                }
    except genshin.errors.GenshinException:
        time.sleep(5)

    # Write dictionary to json file
    with open(cache_file, "w", encoding='utf-8') as file:
        file.write(json.dumps(cache, indent=4))

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

    cache.pop('timestamp')
    output['tooltip'] = tt.heading('Genshin Stats') + '\n' + '\n'.join(
            f'{key}: {value}' for key, value in cache.items()
            if key not in ["Name", "Icon"]
    )
    output['widget'] = cache
    return output


def hsr_module(cache):
    """ Generate waybar output for HSR """
    output = {}
    dailies = cache["Dailies completed"].split("/")
    dailies_completed = int(dailies[0]) == int(dailies[1])

    if not dailies_completed:
        output['class'] = 'red'

    output['text'] = f"{cache['Icon']} {cache['Resin']}"

    cache.pop('timestamp')
    output['tooltip'] = tt.heading('HSR Stats') + '\n' + '\n'.join(
            f'{key}: {value}' for key, value in cache.items()
            if key not in ["Name", "Icon"]
    )
    output['widget'] = cache
    return output


def module(module_config):
    """ Module """
    if 'game' not in list(module_config):
        module_config['game'] = "genshin"
    config = get_config()
    cache = asyncio.run(generate_cache(config, module_config['game']))

    if module_config['game'] == "genshin":
        output = genshin_module(cache['genshin'])
    elif module_config['game'] == "hsr":
        output = hsr_module(cache['hsr'])
    else:
        output = {"text": "Invalid game specified"}

    return output


def main():
    """ Main function """
    args = get_args()
    print(json.dumps(module(args.game), indent=4))


if __name__ == "__main__":
    main()
