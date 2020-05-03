1. RUNNING VIA PYTHON

CallingAllHaters was built to be ran on python 3.7 and may not fully work on other 3.X versions
and will not work at all on python 2.X versions. When running with python, unless you have
already installed all requirements, running run.bat will attempt to install the relevant packages.

2. RUNNING VIA BUILD

In the event that you are unable to use run.bat or you are unable to install python, you should be
able to use the build found in build/exe.win-amd64-3.7 and simply running app.exe will load up the
most recent build. In the event you have changed any source code, running build.bat will make a new
build however this will require python and cx_Freeze.

3. RUNNING THE WEBSITE

When the app.py/.exe starts up, it will attempt to load any default packs within the defaultpacks folder.
Once these packs have loaded up it will attempt to load the actual website under a host and port. The host
and port can only be modified in the python version and not possible in a built version and by default
will use 0.0.0.0 (broadcast) and port 80.

In the event the port is already in use, you may receive an error such as:
OSError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions

An example console output should look like:

INFO:root:Connecting to database
INFO:root:Created and commited any nonexistant databases
INFO:root:Found default card pack location
INFO:root:Found file 'defaultpacks\90's_nostalgia_pack.json'
INFO:root:Successfuly loaded deck with name: 90's Nostalgia Pack
...
Host IP: 192.168.0.50
Running on http://0.0.0.0:80 (CTRL + C to quit)
DEBUG:asyncio:Using selector: SelectSelector
INFO:quart.serving:Running on 0.0.0.0:80 over http (CTRL + C to quit)
[2020-05-03 16:32:19,998] Running on 0.0.0.0:80 over http (CTRL + C to quit)

This means you are able to access the server currently from:
- 192.168.0.50:80 (assuming host is set to 0.0.0.0)
- localhost:80
- 127.0.0.1:80

4. TESTING THE WEBSITE

Test account
USERNAME: test
PASSWORD: test

As the game is multiplayer, you will require atleast 3 different browser instances. An easy way to combat this
is by using a normal chrome tab, an incognito chrome tab and another browser. Using 2 different chrome tabs
will share the same session and count as one user and the same applies to  multiple incognito tabs. This website
will NOT work on Internet Explorer as it does not support ECMAScript 6 (2015) and no support is planned in the
future so another browser like edge or firefox is required. You will need atleast one registered account in
order to test game play and the rest of players are able to be guests. In the event you make a game and it
does not show for guests, refresh the listing.

When a complete game is done, assuming someone has one, all players (not guests) will have the game history added
to their profile and will also have the scores added on the leaderboards. You are able to view your history by
clicking your username in the top bar and a list of app previous games will be played. For guests this list is
empty. You can see an example list when using the test account.