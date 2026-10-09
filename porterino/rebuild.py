# Starts a ReSkate Studio compile of the saved .blend in its own console window, so Blender is not frozen while it runs.
# The window stays open at the end so the result (or the error) can be read.
import os
import subprocess
import tempfile


def is_game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Skate.exe", "/NH"], capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
        return "skate.exe" in out.lower()
    except Exception:
        return False


def start(blend, blender_exe, game_folder, studio_cli, staging_folder, time_of_day="noon", bake=False, open_sky=False,
          launch=True, startup_command="", script_only=False, auto_load=True, before=()):
    """Returns an error message, or None when the build window was started.
    script_only=True writes the build script and returns its path in a tuple (None, path) without running it.
    auto_load=True makes the game go straight into the freshly built map (the level name is read from the map's own
    reskate-levels.json after the build); startup_command, when given, is used instead."""
    game_folder = os.path.normpath(game_folder) if game_folder else ""
    staging_folder = os.path.normpath(staging_folder) if staging_folder else ""
    if not game_folder or not os.path.isdir(os.path.join(game_folder, "Mods")):
        return "Set the game folder (the one with the Mods folder) in Preferences > Add-ons > Porterino"
    if not studio_cli or not os.path.isfile(studio_cli):
        return "Set reskate_cli.exe (inside your ReSkate Studio folder) in Preferences > Add-ons > Porterino"
    if not staging_folder:
        return "Set a build folder in Preferences > Add-ons > Porterino"
    game_abs, stage_abs = os.path.abspath(game_folder).lower(), os.path.abspath(staging_folder).lower()
    if stage_abs == game_abs or stage_abs.startswith(game_abs.rstrip("\\/") + os.sep):
        return "The build folder must be OUTSIDE the game folder (Studio refuses it otherwise)"
    if is_game_running():
        return "skate. is running. Close the game first: a map cannot be replaced while the game has it open"
    name = os.path.splitext(os.path.basename(blend))[0]
    mod_folder = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-") or "My-Map"
    stage = os.path.join(staging_folder, mod_folder)
    # Windows refuses paths over about 260 characters, and the build writes the level's name twice inside the build
    # folder (...\Patch\win32\levels\game\dingolevel_reskate_<name>\dingolevel_reskate_<name>.toc).
    level = "dingolevel_reskate_" + "".join(c if c.isalnum() else "_" for c in name).lower()
    longest = len(os.path.abspath(stage)) + len("\\Patch\\win32\\levels\\game\\") + 2 * len(level) + len("\\.toc") + 12
    if longest > 250:
        return ("The build folder path plus the map name is too long for Windows (%d characters, limit about 250). "
                "Use a short build folder such as C:\\RSBuild, or a shorter .blend name" % longest)
    os.makedirs(stage, exist_ok=True)
    cmd = [studio_cli, "compile-map", game_folder, blend, stage, "--mod-folder", mod_folder, "--blender", blender_exe,
           "--pause-map", "3d", "--time-of-day", time_of_day, "--no-lods"]
    if bake:
        cmd.append("--enlighten")
        if open_sky:
            cmd.append("--enlighten-open-sky")
    cmd.append("--deploy")
    lines = ["@echo off", "title Porterino build: " + name, "echo Building %s ..." % name]
    for extra in before:                                    # steps to run first, each a command list
        lines += [subprocess.list2cmdline(extra),
                  "if errorlevel 1 (echo. & echo PREPARING THE TEST FILE FAILED. Read the lines above. & pause & exit /b 1)"]
    lines += [subprocess.list2cmdline(cmd),
             "if errorlevel 1 (echo. & echo BUILD FAILED. Read the lines above. & pause & exit /b 1)",
             "echo. & echo Installed to Mods\\%s" % mod_folder]
    launcher = os.path.join(game_folder, "ReSkateLauncher.exe")
    if launch and os.path.isfile(launcher):
        if startup_command.strip():
            lines.append('set "RESKATE_STARTUP_COMMANDS=%s"' % startup_command.strip())
            lines.append("echo Game starting with your load command.")
        elif auto_load:
            levels = os.path.join(game_folder, "Mods", mod_folder, "reskate-levels.json")
            lines += ['set "ASSET="',
                      # no pipe in this line: inside the quotes a batch file would pass its escape character along
                      'for /f "usebackq delims=" %%%%A in (`powershell -NoProfile -Command "(ConvertFrom-Json (Get-Content -Raw '
                      '-LiteralPath \'%s\')).levels[0].asset"`) do set "ASSET=%%%%A"' % levels.replace("'", "''"),
                      'if defined ASSET (set "RESKATE_STARTUP_COMMANDS=load %ASSET%;wait 30" & echo Game starting straight into the map.) '
                      'else (echo Could not read the level name: pick the map from the pause menu.)']
        lines.append('start "" /D "%s" "%s" --no-gui --no-update' % (game_folder, launcher))
    lines.append("pause")
    script = os.path.join(tempfile.gettempdir(), "porterino_build_%s.bat" % mod_folder)
    with open(script, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    if script_only:
        return None, script
    subprocess.Popen(["cmd", "/c", script], creationflags=subprocess.CREATE_NEW_CONSOLE)
    return None
