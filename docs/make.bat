@ECHO OFF

pushd %~dp0

set SOURCEDIR=source
set BUILDDIR=build

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Install docs requirements:
	echo.
	echo.    pip install -r docs/requirements.txt
	echo.
	exit /b 1
)

if "%1" == "" goto help

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS%

:end
popd
