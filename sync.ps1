# Copies the packs into Minecraft's development folders. Run INSIDE Windows
# (Parallels):
#
#   powershell -ExecutionPolicy Bypass -File \\Mac\Home\NotWork\frenemy\sync.ps1
#
# Afterwards leaving to the main menu and re-entering the world is enough.
# A full game restart is needed after manifest changes and new sound files.
#
# The source is the raw pack folders, NOT dist: the development loop needs
# no build, and the game ignores versions of development packs.

# The source is the script's own folder: survives any repository rename.
$src = $PSScriptRoot

# After the GDK migration the com.mojang folder moved. The catch: the old UWP
# path still exists on an upgraded install and is EMPTY, copying there
# succeeds and changes nothing.
$new = "$env:APPDATA\Minecraft Bedrock\users\shared\games\com.mojang"
$old = "$env:LOCALAPPDATA\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"
$mc = if (Test-Path $new) { $new } else { $old }
if (-not (Test-Path $mc)) { throw "com.mojang not found, has Minecraft been launched at least once?" }
Write-Host "target: $mc"

# The packs used to be called tato-mod. Old development folders do not vanish
# on their own and would show up in the game as a second set, clean up.
# These two lines can be removed after the first sync.
Remove-Item (Join-Path $mc "development_behavior_packs\tato-mod_bp") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $mc "development_resource_packs\tato-mod_rp") -Recurse -Force -ErrorAction SilentlyContinue

# Copy-Item -Recurse into an EXISTING folder nests a copy inside it, and from
# then on the wrong pack gets edited. So the target is removed first.
$addons = @(
  @{ dir = "bedrock"; slug = "frenemy" }
)
foreach ($addon in $addons) {
  foreach ($pack in @(
      @{ from = "behavior_pack"; to = "development_behavior_packs"; suffix = "bp" },
      @{ from = "resource_pack"; to = "development_resource_packs"; suffix = "rp" })) {
    $dst = Join-Path $mc "$($pack.to)\$($addon.slug)_$($pack.suffix)"
    Remove-Item $dst -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item "$src\$($addon.dir)\$($pack.from)" $dst -Recurse -Force
    Write-Host "  $($addon.dir)\$($pack.from) -> $dst"
  }
}

Write-Host "done. Leave to the main menu and re-enter the world."
