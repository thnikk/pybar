#!/usr/bin/python3
"""
Description: Shows the current OBS scene and changes color if recording.
Uses obsws-python: https://github.com/aatikturk/obsws-python
Author: thnikk
"""
import json
import obsws_python as obs


def main():
    """ Main function """
    try:
        cl = obs.ReqClient(host='localhost', port=4455, password='password')
        status = cl.get_record_status()
        scene = cl.get_current_program_scene().current_program_scene_name
        output = {"text": f" {scene}"}
        if status.output_duration > 0:
            output["class"] = 'green'
            output["tooltip"] = f"{int(status.output_duration/1000)}"
    except ConnectionRefusedError:
        output = {"text": ""}
    print(json.dumps(output))


if __name__ == "__main__":
    main()
