[app]

title = Smart File Manager
package.name = smartfilemanager
package.domain = org.smartfilemanager

source.dir = .
source.include_exts = py,kv,png,jpg

version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE

[buildozer]

log_level = 2
warn_on_root = 1
