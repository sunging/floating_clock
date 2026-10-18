# Changelog

## [0.2.0](https://github.com/sunging/floating_clock/compare/v0.1.0...v0.2.0) (2026-10-18)


### Features

* add detailed alarm configuration ([0012f16](https://github.com/sunging/floating_clock/commit/0012f169ad8461ff247112d49a8a70088ac87a55))
* **alarm:** configurable ring sound and skip ringing when screen is off ([ccc18c2](https://github.com/sunging/floating_clock/commit/ccc18c20d4eb5205220a81369af382e810918855))
* **alarm:** use dropdown hour/minute pickers for alarm time ([b7b492e](https://github.com/sunging/floating_clock/commit/b7b492e87f0475e8a6e27344e2538df7278294bf))
* **app:** launch detached into the background on Windows ([683e4ac](https://github.com/sunging/floating_clock/commit/683e4ac7b07dd0d4e0de4de952f40e95affb217c))
* **autostart:** add start-on-boot support ([7a8b307](https://github.com/sunging/floating_clock/commit/7a8b30715c7f0bc78b4698e5aeb9315f10299f72))
* **clock:** auto-adjust text color to screen background ([8f21d43](https://github.com/sunging/floating_clock/commit/8f21d43c036339aa14629e94cfdc8fde185dd81e))
* **clock:** keep clock and alarm popup within screen bounds ([bae3542](https://github.com/sunging/floating_clock/commit/bae3542fa63a9e27c5ba7bc5a8e08f8106adb1f2))
* **clock:** live appearance preview and drag-to-move ([67104c2](https://github.com/sunging/floating_clock/commit/67104c2ec9740ebc0a21d07ea044abcccf454a37))
* **clock:** scrollable alarm popup with stop button ([38eba4a](https://github.com/sunging/floating_clock/commit/38eba4ad35b0e19cf8353c872cc2c43393d15983))
* **config:** persist settings to config.ini in working directory ([cb17f6a](https://github.com/sunging/floating_clock/commit/cb17f6a5c61df8d1db547e9192313b9f92ffa7f4))
* **config:** store config under program dir instead of cwd ([96791dc](https://github.com/sunging/floating_clock/commit/96791dcaa3de5acb25e34722fde67e2d0414e082))
* implement Windows floating clock (Python + uv + PySide6) ([2b9a844](https://github.com/sunging/floating_clock/commit/2b9a844b07d6666e7ce46dcb2762847ab63ad96f))
* merge native C++ clock and release infrastructure ([80be9ea](https://github.com/sunging/floating_clock/commit/80be9ea433b10e3e664b64b8e96f9fd8d517495c))
* migrate floating clock to C++ and standalone Windows packaging ([ada19a1](https://github.com/sunging/floating_clock/commit/ada19a1a73082c5bbaf15128afe0ff59e891e5f5))
* **settings:** double-click an alarm row to edit it ([28fb33d](https://github.com/sunging/floating_clock/commit/28fb33d615602f246eda0f6e620b7f5b336e9690))
* **settings:** use two-column layout for settings dialog ([c6e6db1](https://github.com/sunging/floating_clock/commit/c6e6db15596edc0bb50f4ed3ab6ad34f2c34cc92))
* Windows floating clock (config file, live preview, drag-to-move) ([6ac5135](https://github.com/sunging/floating_clock/commit/6ac51359e1c50e0c03ff1589a3a601974b0c5f8c))


### Bug Fixes

* **alarm:** fire every alarm due in the same minute ([fbcbb48](https://github.com/sunging/floating_clock/commit/fbcbb4881fa8c52ec1f04f0efc4fa01013566dd7))
* **app:** don't relaunch a frozen exe in the background ([c9ac0c1](https://github.com/sunging/floating_clock/commit/c9ac0c1eecf56828662c8fefb546a492037234c0))
* **clock:** let a click on the alarm popup text stop the alarm ([ea7b075](https://github.com/sunging/floating_clock/commit/ea7b0756626d97c4bcaae26e6f8c3cba5e1d9229))
* **clock:** restore display position without interrupting drags ([0dc73e9](https://github.com/sunging/floating_clock/commit/0dc73e9146f04791052148867f7f19156fa75a84))
* **config:** use user dir for config when installed via pip/uv tool ([4eace76](https://github.com/sunging/floating_clock/commit/4eace76909d059495cbbb5c73c81f179fd1636bf))
* **config:** validate loaded settings and give alarms stable ids ([0c23737](https://github.com/sunging/floating_clock/commit/0c23737aae78be97f81b47b21285a6691bbcfd84))
* resolve Qt SDK warnings and runtime library paths ([102cd75](https://github.com/sunging/floating_clock/commit/102cd75a7c02c0939160fccbfd7927053a93cbff))
* restore clock dragging and refresh adaptive colors immediately ([b098041](https://github.com/sunging/floating_clock/commit/b098041b355f5732c6b03ea3f9922a5f34c6cc2f))
* **settings:** keep settings dialog on-screen under DPI scaling ([99c7e55](https://github.com/sunging/floating_clock/commit/99c7e553f8d19a9576907b9676f61845339f1501))
* tighten reminder popup spacing ([9ffa618](https://github.com/sunging/floating_clock/commit/9ffa6187c143e6b01d38d3e5181d173fe04fbcf0))

## 变更记录

版本记录由 Release Please 的版本 PR 维护。
