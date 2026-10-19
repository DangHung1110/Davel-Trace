# Auto-install Flutter SDK + minimal Android SDK (APK build, no emulator).
# Log: C:/tmp/flutter_install.log. Rerunnable (skips done steps).
# Disk need: ~5GB (16GB free at write time).
set -e
LOG="C:/tmp/flutter_install.log"
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date) start ==="

# 1. Latest stable version (current_release.stable is a HASH -> map to version)
REL=$(curl -s https://storage.googleapis.com/flutter_infra_release/releases/releases_windows.json \
  | python -c "import json,sys; d=json.load(sys.stdin); h=d['current_release']['stable']; r=[x for x in d['releases'] if x['hash']==h][0]; print(r['version'], r['archive'])")
VER=$(echo "$REL" | cut -d' ' -f1); ARC=$(echo "$REL" | cut -d' ' -f2)
echo "stable: $VER ($ARC)"
ZIP="C:/tmp/flutter_dl.zip"
if [ ! -d "C:/src/flutter" ]; then
  rm -f "$ZIP"
  curl -L --fail -o "$ZIP" "https://storage.googleapis.com/flutter_infra_release/releases/download/$ARC" \
    || curl -L --fail -o "$ZIP" "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_${VER}-stable.zip"
  python -c "import zipfile,sys; zipfile.ZipFile('$ZIP').testzip()" \
    || { echo BAD-ZIP; head -c 200 "$ZIP"; exit 1; }
  mkdir -p C:/src
  if command -v unzip >/dev/null; then
    unzip -q "$ZIP" -d C:/src
  else
    powershell.exe -NoProfile -Command "Expand-Archive -Path '$ZIP' -DestinationPath 'C:/src' -Force"
  fi
  rm -f "$ZIP"
else echo "flutter dir exists, skip"; fi
export PATH="C:/src/flutter/bin:$PATH"

# 2. Android cmdline-tools
SDK="C:/Users/ADMIN/AppData/Local/Android/Sdk"
if [ ! -f "$SDK/cmdline-tools/latest/bin/sdkmanager.bat" ]; then
  mkdir -p "$SDK/cmdline-tools"
  CT="C:/tmp/cmdtools.zip"
  [ -f "$CT" ] || curl -L -o "$CT" "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
  if command -v unzip >/dev/null; then
    unzip -q "$CT" -d "$SDK/cmdline-tools"
  else
    powershell.exe -NoProfile -Command "Expand-Archive -Path '$CT' -DestinationPath '$SDK/cmdline-tools' -Force"
  fi
  rm -f "$CT"
  rm -rf "$SDK/cmdline-tools/latest"
  mkdir -p "$SDK/cmdline-tools/latest"
  SRC="$SDK/cmdline-tools/cmdline-tools"
  if [ -d "$SRC/bin" ]; then mv "$SRC/"* "$SDK/cmdline-tools/latest/"; rmdir "$SRC" 2>/dev/null || true
  else echo "unexpected layout:"; ls "$SDK/cmdline-tools"; exit 1; fi
else echo "cmdline-tools exists, skip"; fi
export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
# MSYS JAVA_HOME (/c/...) breaks sdkmanager: force native Windows path
export JAVA_HOME="C:/Program Files/Java/jdk-21.0.11"
export PATH="$SDK/cmdline-tools/latest/bin:$SDK/platform-tools:$PATH"
SDKMAN="$SDK/cmdline-tools/latest/bin/sdkmanager.bat"

# 3. Packages + licenses (no emulator image: debug on physical device)
yes | "$SDKMAN" --licenses >/dev/null 2>&1 || true
"$SDKMAN" "platform-tools" "platforms;android-35" "build-tools;35.0.0"

# 4. Wire up flutter (full path: MSYS PATH lookup is unreliable here)
FLUTTER="C:/src/flutter/bin/flutter"
"$FLUTTER" config --android-sdk "$SDK"
"$FLUTTER" doctor
echo "=== $(date) DONE ==="
