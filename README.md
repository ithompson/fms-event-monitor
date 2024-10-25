# FMS Event Monitor

Tool for monitoring the FRC FMS's match status and reporting match life cycle events like start and end of match.

This tool works by running an instrumented web browser scraping data from the field monitor webpage. It detects changes to the
text on the webpage and decodes those changes into discrete events reporting the match state.

Match state changes are signalled to clients through a websocket server. This websocket server is designed to mimic a portion of the
[Cheesy Arena](https://github.com/Team254/cheesy-arena) API, and also exposes its own dedicated endpoint `/api/match_lifecycle/websocket`
with a custom message type.

Currently, the following states are understood and published to the websocket:
* `WAITING_FOR_PRESTART`: Waiting for a match to be prestarted, or waiting for prestart to complete
* `NOT_READY`: Match not yet read to start
* `READY`: Match ready to start
* `STARTING_MATCH`: Match is starting and is in a pre-autonomous state
* `RUNNING_AUTO`: Match is running in the autonomous phase
* `RUNNING_PERIOD_TRANSITION`: Match is running in the transition period between autonomous and teleop
* `RUNNING_TELEOP`: Match is running in the teleoperated phase
* `FINISHED`: Match is finished, scores not yet posted
* `SCORES_POSTED`: Scores have been posted
* `ABORTED`: Match was aborted before it finished
* Match number changes

# Usage

For basic usage, run `fms-event-monitor` with no arguments. This will connect to FMS at the standard address and expose a websocket server on port 5805.

To change the websocket port, pass the argument `--websocket_port <port_number>`

This tool should only be used on official FRC fields with permission from the event's FTA.

# Installing

This project uses [Playwright](https://playwright.dev/python/) to read the field monitor, which requires additional
setup steps to install the browser internally used.

For Windows and Linux users who want the easiest method, use the appropriate prebuilt package. These packages are standalone portable
binaries with no installation step required.

For MacOS users or other users looking for a more permanent installation, use the Simple installation method.

For developers looking to modify the code, use the Development installation method.

## Prebuilt packages

Standalone single-executable packages for Windows and Linux can be found in this repository's releases page. These packages
come with the required browser bundled into them. MacOS users can follow one of the other installation methods

## Simple installation

Setting up a virtual environment is strongly recommended. Once one is configured, run the following commands to install this program:

```
pip install .
playwright install chromium
```

Once installed, the program `fms-event-monitor` should be available on PATH and runnable.

## Development installation

This project uses hatch. If you do not have it installed already, use the following command:

```
pip install -U hatch
```

Once hatch is installed, run the following command to set up the web browser used for tracking the field monitor:

```
hatch run playwright install chromium
```

To run the project's tests, use the following command:

```
hatch test -a
```

To run lint and style checks, use the following command:

```
hatch fmt
```

# Example websocket output

This is an example of the websocket output for a full match cycle, followed by an aborted match cycle. This data is returned by connecting to the `/api/match_lifecycle/websocket` endpoint on the websocket server exposed by this tool.

```
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'WAITING_FOR_PRESTART', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:23.263615+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'NOT_READY', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:37.157414+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'READY', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:51.058551+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'STARTING_MATCH', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:53.409989+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'RUNNING_AUTO', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:53.415993+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'RUNNING_PERIOD_TRANSITION', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:54:58.490264+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'RUNNING_TELEOP', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:55:01.622350+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'FINISHED', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:55:07.063430+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'SCORES_POSTED', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:56:10.576785+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'WAITING_FOR_PRESTART', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:56:19.334757+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'NOT_READY', 'MatchNumber': 8, 'Timestamp': '2024-10-25T04:56:19.518754+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_NUMBER', 'MatchState': 'NOT_READY', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:19.533756+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'READY', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:34.266703+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'STARTING_MATCH', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:36.918248+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'RUNNING_AUTO', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:36.925238+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'ABORTED', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:41.511302+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'WAITING_FOR_PRESTART', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:42.473631+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'NOT_READY', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:56:52.805802+00:00'}}
{'type': 'matchLifecycle', 'data': {'UpdateType': 'MATCH_STATE', 'MatchState': 'READY', 'MatchNumber': 9, 'Timestamp': '2024-10-25T04:57:01.789426+00:00'}}
```