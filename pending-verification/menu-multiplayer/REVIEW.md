# Review and verification steps for `Menu multiplayer`

## Contents

- [How to verify](#how-to-verify): the commands that reproduce the key evidence
  - [The patch](#the-patch)
  - [Buffers, sending and receiving](#buffers-sending-and-receiving)
  - [Stations and aids](#stations-and-aids)
  - [SystemInfo and keep-alive](#systeminfo-and-keep-alive)
  - [The shared state number](#the-shared-state-number)
  - [SelectMenu, pages, teams and the vote](#selectmenu-pages-teams-and-the-vote)
  - [Miis, profiles, SupplyInfo and friends](#miis-profiles-supplyinfo-and-friends)
  - [Block transfer](#block-transfer)
  - [Scene sequence, tasks and pages](#scene-sequence-tasks-and-pages)
  - [Unnamed engine flags](#unnamed-engine-flags)

## How to verify

Commands run from the repository root; `mk7` is `mk7-llm-research/mk7`. Functions named by this research are given by
address, since they are not in the symbol maps yet.

### The patch

```
git apply --check mk7-llm-research/pending-verification/menu-multiplayer/menu-multiplayer.patch
W=mk7-llm-research/local/work/menu-multiplayer-check
mkdir -p $W/b && cp -r template $W/b/template && (cd $W/b && patch -p1 < ../../../../pending-verification/menu-multiplayer/menu-multiplayer.patch)
mk7 --templates $W/b/template verify --version EUR_REV2
mk7 --templates $W/b/template verify
mk7 --templates $W/b/template struct Net::NetworkSystemInfo
```

### Buffers, sending and receiving

[Findings 1 to 3](README.md#1-creating-the-buffers):

```
mk7 decomp Net::NetworkEngine::createBeforeStructure Net::NetworkBufferController::allocBuffer
mk7 read 0x005f3658 12                       # Net::sNetworkBufferSizes
mk7 dis Net::NetworkBufferController::NetworkBufferController   # +0x4C = 0, +0x4D = 0xFF
mk7 decomp Net::NetworkEngine::calcAfterStructure
mk7 dis 0x0029a2c4 -n 8                      # IMatchingManager::send falls through into NetworkSendPolicy::send
mk7 decomp Net::NetworkSendPolicy::send      # + 0x32 ms when engine + 0x534 is 0
mk7 dis Net::NetworkEngine::sceneEnter | head -30
mk7 decomp Net::WifiMatchingManager::construct Net::LocalMatchingManager::construct   # intervals 0x10 and 0x70
mk7 decomp Net::NetworkSendPolicyUnicast::sendCore_ Net::NetworkSendPolicyBroadcast::sendCore_
mk7 dis Net::NetworkSendPolicyBroadcast::setSendInterval   # lsl #4
mk7 decomp Net::NetworkStationBufferManager::constructSendBuffer_ Net::NetworkStationBufferManager::constructSendHeader_
mk7 decomp Net::NetworkEngine::sendUnreliableCore
mk7 decomp Net::NetworkStationBufferManager::onReceived
mk7 decomp 0x002a4550                        # NetworkBufferController::onReceived
mk7 decomp Net::NetworkBufferController::swapReadBuffer Net::NetworkBufferController::checkAllReceive
mk7 decomp Net::NetworkStationBufferManager::getReadBuffer Net::NetUtil::getRecvDataByPlayerId
mk7 decomp 0x005aa3bc 0x005aa530             # NetworkDataManager<NetworkSelectMenuSendFormat>::onReceived, init
mk7 decomp Net::NetworkSelectMenuDataManager::onReceivedCore
```

### Stations and aids

[Finding 4](README.md#4-stations-aids-and-player-ids):

```
mk7 decomp Net::NetworkStationBufferManager::registStationInfo Net::NetworkStationBufferManager::adjustForAI
mk7 decomp Net::NetworkStationBufferManager::updateConvertTable
mk7 decomp Net::NetworkStationBufferManager::getPlayerId Net::NetworkStationBufferManager::isCpu
mk7 decomp Net::NetworkEngine::updateStationListType_
```

### SystemInfo and keep-alive

[Findings 5 to 7](README.md#5-systeminfo-packets):

```
mk7 decomp Net::NetworkSystemInfoManager::NetworkSystemInfoManager   # stores at system info + 0x208
mk7 decomp Net::NetworkSystemInfo::onReceivedCore                    # writes + 0x1E8 + 4 * aid
mk7 decomp Net::NetworkSystemInfo::updateCore Net::NetworkSystemInfoManager::calc
mk7 decomp Net::NetworkSystemInfoManager::updateLatencyInfo_ Net::NetworkSystemInfoManager::getMasterGameFrame
mk7 decomp Net::NetworkEngine::updatePlayerInfo Net::NetworkEngine::updateStationInfo_
mk7 decomp Net::NetworkSystemInfoManager::isCountPlayerInfoSync Net::NetworkSystemInfoManager::isCountConnectedPlayerInfoSync
mk7 decomp Net::NetworkSystemInfoManager::isCountPlayerInfoSyncReceive Net::NetworkEngine::isMatchInfoSynchronized
mk7 decomp Net::NetworkEngine::checkAllSameSceneReceived Net::NetworkEngine::checkAllRaceSettingReceived
mk7 decomp Net::NetworkEngine::keepAliveChecker_
mk7 decomp Sequence::MenuNetworkSelectMenuTask::onTaskStart Sequence::MenuNetworkApplyTask::onTaskStart   # phases 0x32, 0x34
mk7 decomp Sequence::updateMasterRandom_ Sequence::MenuCommunity_Lobby::onPagePreStep
```

### The shared state number

[Finding 8](README.md#8-the-shared-state-number):

```
mk7 decomp 0x0029959c                       # NetworkStateCalc::receiveState_
mk7 decomp 0x005aa86c                       # NetworkStateManager<NetworkSelectMenuProcess>::executeState
mk7 decomp Net::NetworkStateCalc::updateDisconnect_ Net::NetworkStateCalc::checkAllStationInnerState_
mk7 vtable 0x00625a88                       # the 18 state functions, each a bx lr
mk7 vtable 0x00625604                       # NetworkStateCalc: two pure virtual slots
mk7 decomp Net::NetworkSelectMenuProcess::setSelectStateChange Net::NetworkSelectMenuProcess::startSelect
mk7 decomp Net::NetworkSelectMenuProcess::update Net::NetworkSelectMenuProcess::updateInnerSelectState
mk7 dis Net::NetworkSelectMenuProcess::NetworkSelectMenuProcess | head -40
```

### SelectMenu, pages, teams and the vote

[Findings 9 to 12](README.md#9-selectmenu-packets) and [Finding 24](README.md#24-the-two-ways-out-of-the-settings-pages):

```
mk7 dis Net::NetworkSelectMenuSendFormat::NetworkSelectMenuSendFormat   # start values, the +0x18 array cleared
mk7 decomp Net::NetworkSelectMenuProcess::syncPlayerConfig Net::NetworkSelectMenuProcess::getPlayerStatus
mk7 decomp Sequence::MenuMulti_Mode::buttonHandler_OK Sequence::MenuMulti_Mode::onPagePreStepCore
mk7 decomp Sequence::MenuWiFi_Mode::buttonHandler_OK 0x004851a8          # copyMasterMode_
mk7 decomp 0x005d801c                       # MenuMulti_SyncBase<MenuSingle_Kart>::onPagePreStep
mk7 decomp Sequence::MenuMulti_VSSetting::onPagePreStepCore Sequence::MenuMulti_VSSetting::onCompleteNetwork
mk7 dis Sequence::MenuMulti_VSSetting::buttonHandler_OK                  # 0x004b7b70: r6 = format, stores at +0x58/+0x5c
mk7 decomp Sequence::MenuMulti_VSSetting::updateAppend Sequence::MenuMulti_VSSetting::calcTeam_
mk7 decomp Sequence::checkTeam_ Sequence::checkTeam2_
mk7 xref Net::NetworkSelectMenuProcess::getPlayerStatus --limit 50        # the callers searched for +0x58 / +0x18
mk7 decomp Sequence::updateCourseVoteList_ Sequence::receiveCourseVoteList_ Sequence::registVote_
mk7 decomp Sequence::MenuMulti_CourseVote::onPagePreStep
mk7 decomp Sequence::MenuNetworkCourseDecideTask::onTaskStart Sequence::MenuNetworkCourseDecideTask::onTaskStep
mk7 decomp Sequence::MenuSingle_Setting::buttonHandler_OK Sequence::MenuSingle_Setting::onPageComplete
mk7 decomp UI::LRSelect::apply              # case 3 writes MenuData + 0x669
```

### Miis, profiles, SupplyInfo and friends

[Findings 13 to 16](README.md#13-miis):

```
mk7 vtable 0x00625628 && mk7 vtable 0x00625b00   # Mii and SupplyInfo: no onReceivedCore
mk7 decomp Net::NetworkMiiManager::setupMyMii Net::NetworkMiiStorage::receiveAll
mk7 decomp Net::NetworkPlayerDataManager::receiveCore_ Net::NetworkPlayerDataManager::fixDisconnect
mk7 decomp Net::NetworkSupplyInfoManager::copySetting Net::NetworkSupplyInfoManager::copySettingEx
mk7 decomp Net::NetworkSupplyInfoManager::fixManage 0x002a87e4             # fixManageExtract_
mk7 decomp Net::NetworkSupplyInfoManager::extractRaceSettingToSelectMenu
mk7 decomp Net::NetworkFriendsManager::updateFriendApproachBuffer Net::NetworkFriendsManager::addFriend
mk7 decomp Net::NetworkFriendsManager::checkAllCorrectReceive
```

### Block transfer

[Finding 17](README.md#17-block-transfer-wbt):

```
mk7 decomp RaceSys::CourseArchiveManager::withTrans
mk7 dis 0x00467410 -n 12                    # mov r0, #0 / cmp r0, #0 / beq: the receiving branch is dead
mk7 dis -i dlp 0x00420120 -n 12             # the same test loads 1 in dlp
mk7 decomp Net::NetworkWbtMgr::start Net::NetworkWbtMgr::finishHandler Net::NetworkWbtMgr::calc
mk7 decomp Net::NetworkWbtMgr::Buffer::updateCore Net::NetworkWbtMgr::Buffer::calc
mk7 decomp Net::WbtProtocol::sendHook Net::WbtProtocol::recvHook Net::WbtProtocol::isFinished
mk7 dis Net::NetworkWbtMgr::NetworkWbtMgr   # Object::Actor base, Buffer at + 8, 6 packets per frame
```

### Scene sequence, tasks and pages

[Findings 18 to 23](README.md#18-where-the-network-steps-sit-in-the-scene-sequence):

```
mk7 bseq dump MenuScene-Default             # sections MenuScene, Seq_Multi, Seq_WiFi, Seq_Community, TaskMenu_CourseDecide
mk7 decomp Sequence::MenuNetworkSelectMenuTask::onTaskStart Sequence::MenuNetworkSelectMenuTask::syncPlayerConfig_
mk7 decomp Sequence::MenuMulti_DlplaySequence::calcShakeHands_
mk7 decomp Sequence::MenuWiFi_Waiting::onPagePreStep Sequence::MenuWiFi_WaitingDecide::onPagePreStep
mk7 decomp Sequence::MenuCommunity_Top::onPagePreStep Sequence::MenuNetworkSelectFromWatchTask::onTaskMain
mk7 decomp Sequence::MenuNetworkApplyTask::onTaskStep Sequence::MenuNetworkApplyTask::applyNetworkSetting_
mk7 decomp Sequence::MenuNetworkApplyTask::updatePlayerStatus_ Sequence::MenuNetworkApplyTask::updateOneDriver_
mk7 decomp Sequence::MenuNetworkApplyTask::updateBattleMode_ Sequence::MenuNetworkApplyTask::checkWatchCourse_
```

### Unnamed engine flags

The flags that the document leaves unnamed ([Open questions](README.md#open-questions)), as offsets of
`Net::NetworkEngine`: the guards of `calcAfterStructure` at 0x294 and 0x503, the receive guards at 0x4DA and 0x4DB
(`dataReceiveCallback`, `sendUnreliableCore`), the byte at 0x4B0 that the select menu task and the online pages set,
and the flag at 0xA8 that `MenuWiFi_Waiting` waits for.

```
mk7 decomp Net::NetworkEngine::calcAfterStructure Net::NetworkEngine::dataReceiveCallback
mk7 dis Net::NetworkEngine::sceneEnter | head -8                         # strb r7, [r0, #0x4b0]
mk7 decomp Sequence::MenuWiFi_Waiting::onPagePreStep                     # waits for engine + 0xa8
```
