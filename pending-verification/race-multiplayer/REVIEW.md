# Review and verification steps for `Race multiplayer`

## Contents

- [How to verify](#how-to-verify): the commands that reproduce the key evidence
  - [The patch](#the-patch)
  - [Kart data](#kart-data)
  - [Takeover, goals and ranks](#takeover-goals-and-ranks)
  - [Items and events](#items-and-events)
  - [Start, spectators and end](#start-spectators-and-end)

## How to verify

Commands run from the repository root; `mk7` is `mk7-llm-research/mk7`. Functions without a name in the symbol maps are
given by address.

### The patch

The patch applies on top of the patch of the research on menu multiplayer, not on the bare base commit:

```
W=mk7-llm-research/local/work/race-multiplayer-check
mkdir -p $W/b && cp -r template $W/b/template
(cd $W/b && patch -p1 < ../../../../pending-verification/menu-multiplayer/menu-multiplayer.patch \
         && patch -p1 < ../../../../pending-verification/race-multiplayer/race-multiplayer.patch)
mk7 --templates $W/b/template verify --version EUR_REV2
mk7 --templates $W/b/template verify
mk7 --templates $W/b/template struct Kart::VehicleControlNet
mk7 --templates $W/b/template struct Net::NetworkGameMgr
```

`git apply --check` of `race-multiplayer.patch` alone on the base commit fails on the files the menu patch changes;
on a copy with the menu patch applied it passes.

### Kart data

[Findings 1 to 5](README.md#1-the-kartdata-buffer):

```
mk7 decomp Net::NetUtil::startWriteKartSendBuffer Net::NetUtil::endWriteKartSendBuffer Kart::NetData::send
mk7 decomp 0x002a4ad4                                         # NetworkBufferController::procSplitBuffer_: 4 blocks, 0x22f
mk7 decomp Kart::Director::calcBeforeStructure                 # KartData write end = 0
mk7 decomp Kart::NetData::read Kart::NetData::clear
mk7 decomp Kart::VehicleControlNet::updateNetSend Kart::VehicleControlNet::updateNetSend_Accident
mk7 read 0x002e89c4 9                                          # mask 0x7fff0000, 31, -31, 2500, 50, 256, 1024, 64
mk7 decomp Kart::VehicleControlNet::VehicleControlNet          # layout of the members
mk7 dis Kart::VehicleControlNet::changeToNetSend
mk7 dis 0x002e2330 -n 0x38                                     # calcReact: 4 << id into 0xbdc of both karts
mk7 dis 0x002f36c0 -n 0x34                                     # startThrow: 0x1000 / 0x2000
mk7 dis 0x002db9ac -n 0xac                                     # calcMoveControlCommon replays 0x400..0x2000
mk7 decomp Kart::VehicleBase::VehicleBase                      # net send / recv from CreateArg +0x19
mk7 decomp Kart::Unit::Unit                                    # CreateArg is_cpu / +0x19 in network races
mk7 decomp Kart::VehicleControlNet::updateNetRecv              # long; see README Finding 5
mk7 decomp Kart::VehicleControlNet::applyNetVS Kart::VehicleControlNet::prepareOpenningNetCurtain
mk7 dis 0x00574b40 -n 0x190                                    # static initialiser of sNetRecvParam
```

### Takeover, goals and ranks

[Findings 6 to 8](README.md#6-takeover):

```
mk7 decomp RaceSys::ModeManagerRace::takeoverHandler Kart::Director::changeToAI Kart::Director::changeToNetSend
mk7 decomp Net::NetworkGameMgr::Rank::TakeoverMigration::calc
mk7 read 0x005f3e44 6                                          # 2 1 5 6 4 3
mk7 dis 0x004655c8 -n 0x44                                     # initWait: setEnable(true, play mode == 2)
mk7 decomp Net::NetworkGameMgr::requestGoal Net::NetworkGameMgr::setCurrScore
mk7 decomp Net::NetworkGameMgr::Rank::TakeoverMigration::setTakeoverGoal Net::NetworkGameMgr::isQAidTakeoveredByMe
mk7 decomp Net::NetworkGameDataFormat::NetworkGameDataFormat Net::NetworkGameDataManager::onReceivedCore
mk7 decomp Net::NetworkGameMgr::NetworkGameMgr Net::NetworkGameMgr::initRace Net::NetworkGameMgr::start
mk7 decomp Net::NetworkGameMgr::calc Net::NetworkGameMgr::finalizeRace
mk7 decomp Net::NetworkGameMgr::Rank::Rank Net::NetworkGameMgr::Rank::calc
mk7 decomp Net::NetworkGameMgr::Rank::getRank Net::NetworkGameMgr::Rank::getScore
```

### Items and events

[Findings 9 to 11](README.md#9-itemslot-item-requests):

```
mk7 decomp Net::NetworkItemSlotMgr::request Net::NetworkItemSlotMgr::Buffer::setRequest
mk7 decomp Net::NetworkItemSlotMgr::judgeMyRequest Net::NetworkItemSlotMgr::judgePeerRequest
mk7 decomp Net::NetworkItemSlotMgr::Buffer::isRequestOKFromAll Net::NetworkItemSlotMgr::Buffer::setPeerRequestResult
mk7 dis 0x00291d8c -n 0x30                                     # new(0x26c), then Buffer::Buffer
mk7 decomp Item::GetNum_InItemType_Net Item::GetNum_InItemType
mk7 dis Item::GetNum_InItemType_Net | head -8                  # r1 (the bool) overwritten at once
mk7 decomp Item::ItemDirector::_calcInvalidFlag Item::ItemDirector::_isReserveSeven Item::ItemDirector::_isReserveSevenImpl
mk7 dis 0x005413f0 -n 0x40                                     # sItemTimeParam: 0x708, 0x708 - 0x1e0
mk7 decomp Item::ItemDirector::calcBeforeStructure Item::ItemDirector::initBeforeStructure
mk7 dis Item::ItemDirector::_calcKeyInput_EachPlayer | grep -E '#0x(5c|60|64|68|6c|70)\]'   # timer resets on use
mk7 decomp Item::ItemDirector::_calcNet Item::KartItem::setEquipInfo
mk7 decomp Item::ItemObjBomheiDirector::setBurst Item::ItemDirector::_entryItem
mk7 decomp Net::NetworkItemSlotMgr::Node::init Net::NetworkItemSlotMgr::Buffer::commit Net::NetworkItemSlotMgr::Buffer::onReceivedCore
mk7 dis Net::NetworkEngine::createBeforeStructure | sed -n 271,297p    # new(0x26c), strb at +0x240, str at engine +0x2d0
mk7 decomp Net::NetworkItemSlotMgr::init Net::NetworkItemSlotMgr::initRace Net::NetworkItemSlotMgr::finalizeRace
mk7 dis 0x002d1a98 -n 0x6c                                     # ItemSlot::stateSpin: stock, getStockItemType, _setStockItem
mk7 decomp Net::NetworkItemSlotMgr::stock Net::NetworkItemSlotMgr::clear Net::NetworkItemSlotMgr::getStockItemType
mk7 decomp Net::NetworkItemSlotMgr::Buffer::setStockItemType Net::NetworkItemSlotMgr::Buffer::setEquipItemType
mk7 decomp Net::NetworkItemSlotMgr::GetNumStockItem Net::NetworkItemSlotMgr::GetNumEquipItem
mk7 decomp Net::NetworkItemSlotMgr::updateMyKartStockState Net::NetworkItemSlotMgr::updateMyKartEquipState
mk7 decomp Net::NetworkEventModule::setSendEvent Net::NetworkEventModule::CreateSendBuffer
mk7 decomp Net::NetworkEventModule::recvHook Net::NetworkEventModule::calc Net::NetworkEventModule::init
mk7 dis Net::NetworkItemEventDataMgr::postInit                 # init(0x200, 0x7e, 0x2a, handler)
mk7 dis Net::NetworkGameEventMgr::Buffer::postInit             # init(0x40, 0x18, 0x22, handler)
mk7 decomp Net::NetworkItemEventMgr::initRace Net::NetworkEventModule::finalizeRace
mk7 decomp Net::NetworkItemEventDataMgr::setSendEvent Net::NetworkItemEventDataMgr::eventHandler
mk7 decomp Net::NetworkItemEventDataMgr::updateCore Net::NetworkItemEventDataMgr::onReceivedCore
mk7 xref Net::NetworkItemEventDataMgr::setSendEvent           # the 13 senders
mk7 decomp Item::ItemObjBase::stateInitUse Item::ItemObjBase::stateSelfMove Item::ItemObjBase::updateKartItem_EquipItemExit
mk7 decomp Item::ItemObjTail::stateInitSpin Item::ItemObjBomhei::stateInitBurst Item::ItemObjBomhei::_calcSearch
mk7 decomp Item::ItemObjKouraB::searchKart Item::ItemObjKouraR::searchKart
mk7 decomp Item::ItemObjSevenDirector::_sendEvent Item::ItemObjSevenDirector::entry
mk7 decomp Item::ItemDirector::_itemEventRecvHandler          # one branch per event type
```

### Start, spectators and end

[Findings 12 to 14](README.md#12-starting-the-race-together):

```
mk7 decomp RaceSys::ModeManagerRace::initWait RaceSys::ModeManagerRace::calcWait
mk7 decomp Net::NetworkSystemInfoManager::Sync::ready      # 0xbb8 = 3000 into NetworkSystemInfo + 0xee
mk7 read 0x002aa664 1
mk7 decomp Net::NetworkSystemInfoManager::Sync::stateReady Net::NetworkSystemInfoManager::Sync::stateSync
mk7 decomp Net::NetworkSystemInfoManager::NetworkSystemInfoManager   # Sync at +0x248, FrameSync at +0x24c
mk7 decomp Net::NetworkSystemInfoManager::startWatchFrameSync Net::NetworkSystemInfoManager::FrameSync::calc
mk7 decomp RaceSys::ModeManagerBase::stateInitGoal Kart::Director::changeToAI_NetStop_All Kart::Unit::changeToNetStop
```
