py build.py build

mkdir "build/exe.win-amd64-3.7/defaultpacks"
xcopy /D defaultpacks "build/exe.win-amd64-3.7/defaultpacks"
mkdir "build/exe.win-amd64-3.7/static"
xcopy /D static "build/exe.win-amd64-3.7/static"
mkdir "build/exe.win-amd64-3.7/templates"
xcopy /D templates "build/exe.win-amd64-3.7/templates"

pause