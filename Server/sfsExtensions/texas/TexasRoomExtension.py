#-*- coding: utf-8 -*-
#
# Simple Python Extension
# v 1.0.0
#
import it.gotoandplay.smartfoxserver.exceptions as __exceptions
import it.gotoandplay.smartfoxserver.util.scheduling as __scheduling

import random
import sys, os
import datetime

importPath = os.path.abspath("sfsExtensions/texas")
if not (importPath in sys.path):
    sys.path.append(importPath)

from HandEvaluator import *
from texaslib.db import Model
from texaslib.models.texasplayer import TexasPlayer
from texaslib.models.texasconfig import TexasConfig
from texaslib.logics.dealer import Dealer
from HandEvaluator import makeRequest
from texaslib.texasutils import texasroomutils

ACTION_OUT_GAME, ACTION_START, ACTION_FOLD, ACTION_CHECK, ACTION_CALL, ACTION_RAISE, ACTION_ALL_IN = range(7)

class SeatInfo:
    def __init__(self, seatId):
        self.seatId = seatId
        self.userId = -1
        self.action = ACTION_OUT_GAME
        self.chips = 0
        self.sitChips = 0
        self.chipsIn = 0
        self.card1 = -1
        self.card2 = -1
        self.hand = Hand()
        self.oldUserId = -1
        self.oldUserName = None
        self.timeoutCount = 0
        self.experience = 0
        self._texas_player = None
    
    def _get_texas_player(self):
        if self.userId <= -1:
            return None
        who = _server.getUserById(self.userId)
        if not who:
            return None
        if self._texas_player and self._texas_player.userId == who.getName():
            return self._texas_player
        self._texas_player = TexasPlayer.get(who.getName())
        return self._texas_player
    
    poker_player = property(_get_texas_player)
    
    def getSeatVar(self):        
        if len(self.hand.cards) > 0:            
            return "%".join([str(self.userId), str(self.action), str(self.chips), str(self.chipsIn), \
            str(self.card1), str(self.card2), str(self.hand.get_type()), \
            str(self.hand.ranks[0]), str(self.hand.ranks[1]), str(self.hand.ranks[2]), str(self.hand.ranks[3]), str(self.hand.ranks[4])])
        return "%d%%%d%%%d%%%d" % (self.userId, self.action, self.chips, self.chipsIn)
        
    def userSit(self, userId, sitChips):
        global waitUserActionTask
        self.userId = userId
        self.action = ACTION_OUT_GAME
        self.chips = sitChips
        self.sitChips = sitChips
    
        self.updateSeatVar()

        self.timeoutCount = 0
        
        # when game is not start, check whether need to start game
        playerCount = texasroomutils.room_player_count(_server)
        round = texasroomutils.room_round(_server)
        if (round == 0) and (playerCount > 1) and (playerCount <= 9) and (waitUserActionTask == None):
            startGameStartTask(5)
        
    def userStand(self, who = None):
        hasLeftRoom = True
        if who == None:
            hasLeftRoom = False
            who = _server.getUserById(self.userId)
        
        if (not hasLeftRoom) and (who != None):
            _server._helper.switchPlayer(who, _server.getCurrentRoom().getId(), True)    

        # reset user's coin to database
        userInfo = self.poker_player
        if userInfo != None :
            if userInfo.coin < 0 :
                now = datetime.datetime.now()
                userInfo.times += 1
                if now.date() == userInfo.resetCoinTime.date() :
                    if userInfo.times <= 3 :
                        winChips = 1000
                        response = ["coinReset",str(userInfo.times),str(winChips),'0']
                        _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
                    else :
                        winChips = 0
                else:
                    winChips = 1000
                    userInfo.times = 1
                userInfo.resetCoinTime = now
                userInfo.coin = winChips
                userInfo.put()
        else:
            _server.trace("serverError, user delete game")
        
    
        # game is not started
        _round = texasroomutils.room_round(_server)
        if _round == 0:
            self.userId = -1
            self.action = ACTION_OUT_GAME
            self.chips = 0
            self.sitChips = 0
            
            self.updateSeatVar()
            
            # stop the timer which is about to start the game            
            playerCount = texasroomutils.room_player_count(_server)
            if (playerCount < 2):
                stopAllTasks()
                
        else:
            if self.action != ACTION_OUT_GAME:
                self.oldUserId = self.userId
                if who != None:
                    self.oldUserName = who.getName()
            
            self.userId = -1
            self.action = ACTION_OUT_GAME
            
            self.updateSeatVar()
            
            if checkWaitChipInTaskRunning(self.seatId):
                # stand when task is waiting me to chipin
                stopAllTasks()
                
                if not checkGameOrRoundOver():                
                    beginNextChipIn(self.seatId)
            elif (not checkGameOrRoundOver()) and (self.timeoutCount >= 2):
                beginNextChipIn(self.seatId)
        
        # notify client when auto kick out of the game from server
        if (self.timeoutCount >= 3) and (who != None):
            response = ["forceStand"]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
                
        self.timeoutCount = 0

        if (not hasLeftRoom) and (who != None) and (not who.isSpectator()):
            _server.joinRoom(who, _server.getCurrentRoom().getId(), True, _server.getCurrentZone().getAutoJoinRoom())
        
    def reset(self):        
        self.userId = -1
        self.action = 0
        self.chips = 0
        self.sitChips = 0
        self.chipsIn = 0
        self.card1 = -1
        self.card2 = -1
        self.hand = Hand()
        self.oldUserId = -1
        self.oldUserName = None
        self.timeoutCount = 0
        self.experience = 0 
    def updateSeatVar(self):
        
        seatVar = RoomVariable("seat" + str(self.seatId), self.getSeatVar(), True, True)
        _server.setRoomVariables(_server.getCurrentRoom(), None, [seatVar])
        
class WaitUserActionTaskHandler(__scheduling.ITaskHandler):    
    def doTask(self, task):
        global waitUserActionTask
    
        action = task.id["action"]        
        
        if action == "startGame":
            task.active = False
            waitUserActionTask = None
            startGame()
        elif action == "waitchipin":
            chipInSeatId = int(task.id["chipInSeatId"])
            task.active = False
            waitUserActionTask = None
            
            # check timeout count, whether need to auto kick out of the game
            chipInSeatInfo = seats[chipInSeatId]                
            if (chipInSeatInfo.userId > -1) and (chipInSeatInfo.action not in [0, 2, 6]):
                chipInSeatInfo.timeoutCount += 1
                
                if (chipInSeatInfo.timeoutCount >= 3):                
                    chipInSeatInfo.userStand()
                    return
                
            doFoldAction(chipInSeatId)

def init():
    _server.trace("Python texas room extension starting")

    global bigBlindSeatId
    global smallBlindSeatId
    global pots
    global boardCards

    global seats
    global cards
    
    global buyInMax
    global buyInMin
    global bigBlind
    
    global minChipIn
    global maxChipIn    
    
    global scheduler
    global waitUserActionTaskHandler
    global waitUserActionTask

    Model.db = _server.getDatabaseManager()
   
    maxChipIn = 0

    bigBlindSeatId = 0
    smallBlindSeatId = 0
    pots = []
    boardCards = []
    round = 0

    # init 9 seats
    seats = dict([(seatId, SeatInfo(seatId)) for seatId in range(9)])
    
    # init all 52 cards
    cards = range(52)

    bigBlind = int(_server.getCurrentRoom().getName().split("_").pop())
    buyInMin = bigBlind * 10
    buyInMax = bigBlind * 200    
    
    scheduler = __scheduling.Scheduler()
    scheduler.startService()
    
    waitUserActionTaskHandler = WaitUserActionTaskHandler()
    waitUserActionTask = None
    
def destroy():
    global scheduler
    
    del sys.modules["HandEvaluator"]
    
    scheduler.destroy(None)

    _server.trace("Python texas room extension stopping")
    
    
def handleRequest(cmd, params, who, roomId, protocol):
    global buyInMin, buyInMax

    if (cmd == "sit") and (protocol == _server.PROTOCOL_STR):
        seatId = int(params[0])
        buyInChips = int(params[1])
        
        #_server.trace("request sit in seat " + str(seatId))
        
        if (seatId < 0) or (seatId >=9):
            return
        
        # check cheating
        if buyInChips < buyInMin:
            buyInChips = buyInMin
        elif buyInChips > buyInMax:
            buyInChips = buyInMax
        
        response = None
        
        if seats[seatId].userId > -1:
            response = ["sitKO", "E0014"]
        else:
            # get current coin from database
            coin = None
            player = TexasPlayer.get(who.getName())
            if player:
                coin = player.coin
            
            if coin == None:
                response = ["serverError", "E0021"]
            elif coin < buyInChips:
                response = ["sitKO", "E0013"]
            else:
                _server.switchSpectator(who, roomId)
            
                if who.isSpectator():
                    response = ["sitKO", "E0014"]
                    
        if not response == None:
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
            
        else:            
            seatInfo = seats[seatId]        
            
            seatInfo.userSit(who.getUserId(), buyInChips)
            
    elif (cmd == "stand") and (protocol == _server.PROTOCOL_STR):
        seatId = int(params[0])
        uid = who.getUserId()
        
        if (seatId < 0) or (seatId >= 9):
            return
        else:
            seatInfo = seats[seatId]
            if (seatInfo.userId == uid):
            
                seatInfo.userStand()                


    elif (cmd == "chipin") and (protocol == _server.PROTOCOL_STR):
        action = int(params[0])
        chipsIn = int(params[1])
    
        # check cheating
        if action not in [2, 3, 4, 5, 6]:
            _server.trace("cheating, chipin action type error")
            return
    
        uid = who.getUserId()
        
        isUserSit = False
        for seatId, seatInfo in seats.iteritems():
            if seatInfo.userId == uid:        
                isUserSit = True
                
                if checkWaitChipInTaskRunning(seatId):                
                    stopAllTasks()
                    
                    # reset timeoutCount when user perform any actions
                    seatInfo.timeoutCount = 0
                
                    # call
                    if action == 4:
                        doCallAction(seatId)                    
                    # fold
                    elif action == 2:
                        doFoldAction(seatId)
                    # check
                    elif action == 3:
                        doCheckAction(seatId)
                    # raise or all-in
                    elif (action == 5) or (action == 6):
                        doRaiseAction(seatId, chipsIn)
                else:
                    _server.trace("error, it's not the turn to chipin for seat" + str(seatId))
                    
                break
                
        if not isUserSit:
            _server.trace("error, can not request chipin when user is not sit in any seat")
    
    elif (cmd == "sendface") and (protocol == _server.PROTOCOL_STR):
        global bigBlind,maxChipIn

        seatId = int(params[0])
        message = str(params[1]) 

        kinds = message[0:1]
        face = message[2:]   
        result = 0

        if seatId < 0 or seatId > 8 :
            result = -3
        else :
            # "A" no limit 
            if kinds in ['A']:
                result = 1
            # "B" is coin limit
            elif kinds in ['B']:  
                result = limitByCoin(who.getName(),kinds)
            # "C" "E" is coin and level limit    
            elif kinds in ['C','E']: 
                result = limitByCoinAndExp(who.getName(),kinds)  
            #  "D" "F" is vip limit        
            else:
                result = -3
        
        
        if result > 0:
            need_coin = 0
            seatInfo = seats[seatId]
            if kinds in ['B','C']:
                need_coin = bigBlind/2

            elif kinds in ['E']:
                need_coin = bigBlind
                
            if seatInfo.chips >= need_coin :
                seatInfo.chips = seatInfo.chips - need_coin
                seatInfo.sitChips = seatInfo.sitChips - need_coin
                maxChipIn = maxChipIn - need_coin
            else:
                result = -1
        
        if result > 0:
            _server._helper.dispatchPublicMessage(face, _server.getCurrentRoom(), who)
            response = ["faceUpdate",str(seatId),str(seatInfo.chips),str(need_coin)]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
        else:
            data = {
               -100:"E0032",
               -1:"E0034",
               -2:"E0033",
               -3:"E0000"
            }
            response = {}
            response["_cmd"] = "sendFaceKo"
            response["state"] = data[result]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_JSON)
            

def handleInternalEvent(evt):
    global seats, buyInMin, buyInMax

    evtName = evt.getEventName()

    if (evtName == "userExit") or (evtName == "userLost") or (evtName == "logOut"):
        uid = int(evt.getParam("uid"))
        who = evt.getObject("user")
        
        for seatId, seatInfo in seats.iteritems():        
            if seatInfo.userId == uid:
                seatInfo.userStand(who)

    elif (evtName == "userJoin"):
        user = evt.getObject("user")
        room = evt.getObject("room")

        for seatId, seatInfo in seats.iteritems():
            if seatInfo.userId > -1:
                seatInfo.hand = Hand()
                seatInfo.updateSeatVar()
        # quick join and sit
        if not user.isSpectator():
            # get current coin from database
            coin = None
            player = TexasPlayer.get(user.getName())
            if player:
                coin = player.coin
            
            response = None
            
            if coin == None:
                response = ["serverError", "E0021"]
            elif coin < buyInMin:
                response = ["sitKO", "E0019"]
            else:
                sitSuccess = False
                for seatId, seatInfo in seats.iteritems():
                    if seats[seatId].userId == -1:                                     
                        if coin <= buyInMin * 10:
                            seatInfo.userSit(user.getUserId(), coin)
                            sitSuccess = True
                            break
                        else:
                            seatInfo.userSit(user.getUserId(), buyInMin * 10)
                            sitSuccess = True
                            break      
                        
                if not sitSuccess:
                    response = ["sitKO", "E0020"]
                    
            if not response == None:
                _server._helper.switchPlayer(user, room.getId(), True)            
                
                if not user.isSpectator():
                    _server.joinRoom(user, room.getId(), True, _server.getCurrentZone().getAutoJoinRoom())
                    
                _server.sendResponse(response, -1, None, [user], _server.PROTOCOL_STR)
        

def stopAllTasks():
    global waitUserActionTask

    if not waitUserActionTask == None:                    
        waitUserActionTask.active = False
        waitUserActionTask = None
        
def checkWaitChipInTaskRunning(chipInSeatId):
    global waitUserActionTask
    
    if (not waitUserActionTask == None) and (waitUserActionTask.id["action"] == "waitchipin") \
    and (chipInSeatId == int(waitUserActionTask.id["chipInSeatId"])):
        return True
    
    return False
        
def startGameStartTask(wait):
    global waitUserActionTask, scheduler, waitUserActionTaskHandler

    waitUserActionTask = __scheduling.Task({"action":"startGame"})
        
    scheduler.addScheduledTask(waitUserActionTask, wait, False, waitUserActionTaskHandler)
    
def startWaitChipInTask(chipInSeatId):
    global waitUserActionTask, scheduler, waitUserActionTaskHandler

    waitUserActionTask = __scheduling.Task({"action":"waitchipin", "chipInSeatId":str(chipInSeatId)})        
    scheduler.addScheduledTask(waitUserActionTask, 22, False, waitUserActionTaskHandler)
    
                
def startGame():
    global bigBlindSeatId, smallBlindSeatId, bigBlind, cards, boardCards, minChipIn, maxChipIn, pots

    round = texasroomutils.room_round(_server)
    if round > 0:
        _server.trace("unhandled error, game already started")
        return
    
    # check out of chips user
    for seatId, seatInfo in seats.iteritems():    
        # auto stand when user is out of chips
        if (seatInfo.userId > -1) and (seatInfo.chips == 0):                
            seatInfo.userStand()

    playerCount = texasroomutils.room_player_count(_server)
    if playerCount < 2:
        _server.trace("not enought user to start the game")
        return
    
    _server.trace("Room %d: game start" % (_server.getCurrentRoom().getId()))
    round = 1
    
    # shuffle cards
    random.shuffle(cards)
    roomVarList = []
    
    texas_config = TexasConfig.get("dealer_config")
    dealer_config = {}
    if texas_config and texas_config.config:
        dealer_config = texas_config.config
    _dealer = Dealer(seats, dealer_config)
    _dealer.send_hand_poker()
    
    # update seatInfo to playing status, assign hole cards to each player
    for seatId, seatInfo in seats.iteritems():
        if seatInfo.userId > -1:
            response = ["preflop", str(seatInfo.card1), str(seatInfo.card2)]                
            who = _server.getUserById(int(seatInfo.userId))            
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
        else :
            seatInfo.reset()
            
    # update dealer index
    #_server.trace("old dealer" + str(dealerSeatId))
    dealerSeatId = getNextSeatIdInPlaying(texasroomutils.room_dealer(_server))
            
    # init board cards
    boardCards = _dealer.send_board_poker()
    _dealer.poker.reset()
    
    # reset pots
    for potId, pot in enumerate(pots):
        roomVarList.append(RoomVariable("pot" + str(potId), "", True, True))
    pots = []
    
    # init game status vars        
    roomVarList.append(RoomVariable("round", round, True, True))
    roomVarList.append(RoomVariable("dealer", dealerSeatId, True, True))
    roomVarList.append(RoomVariable("cards", "", True, True))
    
    # find small/big blind seat index
    if playerCount == 2:
        smallBlindSeatId = dealerSeatId        
    else:
        smallBlindSeatId = getNextSeatIdInPlaying(dealerSeatId)    
    bigBlindSeatId = getNextSeatIdInPlaying(smallBlindSeatId)
    
    # auto chip in for small blind
    smallBlindSeatInfo = seats[smallBlindSeatId]
    if smallBlindSeatInfo.chips <= (bigBlind / 2):
        smallBlindSeatInfo.chipsIn = smallBlindSeatInfo.chips
        smallBlindSeatInfo.chips = 0
        smallBlindSeatInfo.action = 6
    else:
        smallBlindSeatInfo.chipsIn = bigBlind / 2
        smallBlindSeatInfo.chips = smallBlindSeatInfo.chips - smallBlindSeatInfo.chipsIn
        
    # auto chip in for big blind
    bigBlindSeatInfo = seats[bigBlindSeatId]
    if bigBlindSeatInfo.chips <= bigBlind:
        bigBlindSeatInfo.chipsIn = bigBlindSeatInfo.chips
        bigBlindSeatInfo.chips = 0
        bigBlindSeatInfo.action = 6
    else:
        bigBlindSeatInfo.chipsIn = bigBlind
        bigBlindSeatInfo.chips = bigBlindSeatInfo.chips - bigBlindSeatInfo.chipsIn
    
    if bigBlindSeatInfo.chipsIn > smallBlindSeatInfo.chipsIn:
        minChipIn = bigBlindSeatInfo.chipsIn
    else:
        minChipIn = smallBlindSeatInfo.chipsIn    
    
    for seatId, seatInfo in seats.iteritems():    
        roomVarList.append(RoomVariable("seat" + str(seatId), seatInfo.getSeatVar(), True, True))
        
    # broadcast roomVars to clients
    _server.setRoomVariables(_server.getCurrentRoom(), None, roomVarList)
    
    if not checkGameOrRoundOver():        
        beginNextChipIn(bigBlindSeatId)

    
# return the next in game seatId who is closest to the currentSeatId on a clockwise direction        
def getNextSeatIdInPlaying(currentSeatId):
    nextSeatId = (currentSeatId + 1) % 9
    #_server.trace("find" + str(nextSeatId))
    # 0: not in game or just quit game
    # 2: fold
    # 6: all-in
    while seats[nextSeatId].action in [0, 2, 6]:
        nextSeatId = (nextSeatId + 1) % 9
        #_server.trace("find" + str(nextSeatId))
        if nextSeatId == currentSeatId:
            if seats[nextSeatId].action in [0, 2, 6]:
                return None
            else:
                #_server.trace("found" + str(nextSeatId))
                return nextSeatId
                
    #_server.trace("found" + str(nextSeatId))
    return nextSeatId
    
def doFoldAction(seatId):
        
    if seats[seatId].action not in [0, 2, 6]:
        seatInfo = seats[seatId]
        seatInfo.action = 2    
        
        seatInfo.updateSeatVar()        
        
        if not checkGameOrRoundOver():
            beginNextChipIn(seatId)            
        
    else:
        _server.trace("error, can not do fold action when seat is empty or player in seat already quit, fold or all-in")

def doCheckAction(seatId):
    global seats
    
    if seats[seatId].action not in [0, 2, 6]:
        seatInfo = seats[seatId]
        seatInfo.action = 3
        
        seatInfo.updateSeatVar()
        
        round = texasroomutils.room_round(_server)
        if seatId == texasroomutils.room_dealer(_server):
            if round == 4:
                endGame()
            else:
                beginNextRound()
        else:
            nextSeatId = getNextSeatIdInPlaying(seatId)
            if (not nextSeatId == None) and (nextSeatId != seatId) and (seats[nextSeatId].action == ACTION_START):
                beginNextChipIn(seatId)
            elif round == 4:
                endGame()
            else:                
                beginNextRound()
    else:
        _server.trace("error, can not do check action when seat is empty or player in seat already quit, fold or all-in")
    
def doCallAction(seatId):
    global minChipIn, seats

    if seats[seatId].action not in [ACTION_OUT_GAME, ACTION_FOLD, ACTION_ALL_IN]:
        seatInfo = seats[seatId]
        
        if (seatInfo.chips + seatInfo.chipsIn) > minChipIn:
            seatInfo.chips = seatInfo.chips + seatInfo.chipsIn - minChipIn
            seatInfo.chipsIn = minChipIn
            seatInfo.action = ACTION_CALL
        else:
            seatInfo.chipsIn = seatInfo.chips + seatInfo.chipsIn
            seatInfo.chips = 0
            seatInfo.action = ACTION_ALL_IN
            
        seatInfo.updateSeatVar()
        
        #_server.trace("call" + str(seatId))
        if not checkGameOrRoundOver():
            beginNextChipIn(seatId)    
        
    else:
        _server.trace("error, can not do call action when player in seat already quit, fold or all-in")

def doRaiseAction(seatId, chipsIn):
    global minChipIn, maxChipIn, seats

    if seats[seatId].action not in [0, 2, 6]:
        seatInfo = seats[seatId]
        
        minRaiseChipIn = minChipIn * 2
        
        if minRaiseChipIn < maxChipIn:
            if chipsIn < minRaiseChipIn:
                chipsIn = minRaiseChipIn
            elif chipsIn > maxChipIn:
                chipsIn = maxChipIn
        elif minChipIn < maxChipIn:
            if maxChipIn < (seatInfo.chips + seatInfo.chipsIn):
                chipsIn = maxChipIn
            else:
                chipsIn = seatInfo.chips + seatInfo.chipsIn        
        else:
            _server.trace("error, should send call request instead of raise request")
            return
        
        seatInfo.chips = seatInfo.chips + seatInfo.chipsIn - chipsIn
        seatInfo.chipsIn = chipsIn
        
        # update minChipIn after the raise
        minChipIn = seatInfo.chipsIn
        
        if seatInfo.chips == 0:
            seatInfo.action = 6
        else:
            seatInfo.action = 5
        
        seatInfo.updateSeatVar()
        
        #when one player raise, other player must call, re-raise or fold
        beginNextChipIn(seatId)
    else:
        _server.trace("error, can not do raise action when seat is empty or player in seat already quit, fold or all-in")

def beginNextChipIn(seatId):
    global minChipIn, maxChipIn
    
    stopAllTasks()
    
    nextChipInSeatId = getNextSeatIdInPlaying(seatId)
    #_server.trace("nextChipInSeatId" + str(nextChipInSeatId))
    if (not nextChipInSeatId == None) and (nextChipInSeatId != seatId):
    
        nextChipInSeatInfo = seats[nextChipInSeatId]
                
        if minChipIn == 0:
            minRaiseChipIn = bigBlind
        else:
            minRaiseChipIn = minChipIn * 2
            
        # raise can only happen when at least two player is not quit, fold or all-in
        maxChipIn = 0
        for seatId, seatInfo in seats.iteritems():
            if (seatInfo.action not in [0, 2, 6]) and (seatInfo.seatId != nextChipInSeatId):
                if (seatInfo.chips + seatInfo.chipsIn) > maxChipIn:
                    maxChipIn = seatInfo.chips + seatInfo.chipsIn
                        
        if (nextChipInSeatInfo.chips + nextChipInSeatInfo.chipsIn) < maxChipIn:
            maxChipIn = nextChipInSeatInfo.chips + nextChipInSeatInfo.chipsIn
                
        chipinStr = "%".join([str(nextChipInSeatId), str(minChipIn), str(minRaiseChipIn), str(maxChipIn)])        
        
        # broadcast roomVars to clients
        _server.setRoomVariables(_server.getCurrentRoom(), None, [RoomVariable("startchipin", chipinStr, True, True)])
            
        # start wait chipin timer
        startWaitChipInTask(nextChipInSeatId)        
            
    else:
        _server.trace("error, where must be more than one player who is not quit, fold or all-in when begin next chipin")
        
def beginNextRound():
    global boardCards, minChipIn, bigBlind, seats
    
    stopAllTasks()
    round = texasroomutils.room_round(_server)
    round += 1
    
    roomVarList = []    
    roomVarList.append(RoomVariable("round", round, True, True))
    roomVarList.append(RoomVariable("startchipin", "", True, True))
    
    # deal board cards    
    if len(boardCards) >= round + 1:
        boardCardVar = "%".join([str(boardCards[i]) for i in range(round+1)])
    
    roomVarList.append(RoomVariable("cards", boardCardVar, True, True))
    
    # assign pots
    roomVarList.extend(assignPots())
    
    # return extra chips in to each player, there should be no extra chips in except when game is over
    for seatId, seatInfo in seats.iteritems():
        if seatInfo.chipsIn > 0:
            _server.trace("error, when the game is not over, there should be no extra chips after assign pots")
            seatInfo.chipsIn = 0
            
        if seatInfo.action not in [0, 2, 6]:
            seatInfo.action = 1
            
        roomVarList.append(RoomVariable("seat" + str(seatId), seatInfo.getSeatVar(), True, True))                
        
    _server.setRoomVariables(_server.getCurrentRoom(), None, roomVarList)
    
    minChipIn = 0
        
    beginNextChipIn(texasroomutils.room_dealer(_server))
    
def checkGameOrRoundOver():
    global seats, bigBlindSeatId, smallBlindSeatId, minChipIn

    aliveSeatCount = 0        
    notCallSeatCount = 0
    allinSeatCount = 0
    betSeatCount = 0
    
    for sId, seatInfo in seats.iteritems():
        if seatInfo.action == ACTION_ALL_IN:
            allinSeatCount = allinSeatCount + 1
            betSeatCount = betSeatCount + 1
    
        if seatInfo.action not in [ACTION_OUT_GAME, ACTION_FOLD, ACTION_ALL_IN]:
            aliveSeatCount = aliveSeatCount + 1
            betSeatCount = betSeatCount + 1
            
            if seatInfo.chipsIn < minChipIn:
                notCallSeatCount = notCallSeatCount + 1
                
    round = texasroomutils.room_round(_server)
    if (aliveSeatCount == 0) or (aliveSeatCount == 1 and notCallSeatCount == 0) \
    or (aliveSeatCount == 1 and allinSeatCount == 0) or (notCallSeatCount == 0 and round == 4):
        if betSeatCount == 1:
            endGame(False)
        else:
            endGame()
        return True
        
    elif (notCallSeatCount == 0) and (round == 1) \
    and (seats[bigBlindSeatId].action == ACTION_START or seats[smallBlindSeatId].action == ACTION_START):
        return False
        
    elif (notCallSeatCount == 0) and (round != 4):
        beginNextRound()
        return True
            
    else:
        return False
    
def assignPots():
    global pots

    chipsInList = []
    for seatId, seatInfo in seats.iteritems():
        # players who call, raise or all-in with more than 0 chipsIn remains could win the pots
        if (seatInfo.action in [ACTION_START, ACTION_CALL, ACTION_RAISE, ACTION_ALL_IN]) \
        and (seatInfo.chipsIn > 0) and (seatInfo.chipsIn not in chipsInList):
            chipsInList.append(seatInfo.chipsIn)
    
    assignedChips = 0
    
    if len(chipsInList) > 0:
        chipsInList.sort()
        
        for chipsIn in chipsInList:        
            toBeAssignedChips = chipsIn - assignedChips
            assignedChips = chipsIn
            
            unfinishedLastPot = None            
            if len(pots) > 0:
                unfinishedLastPot = pots.pop()
            else:
                unfinishedLastPot = []
            
            potChips = 0
            potSeats = [0]*9
            if len(unfinishedLastPot) > 0:
                potChips = unfinishedLastPot[0]
                potSeats = unfinishedLastPot[1:]
                
            hasSomeoneAllIn = False
            
            for seatId, seatInfo in seats.iteritems():
                if seatInfo.chipsIn > 0:
                
                    if seatInfo.chipsIn < toBeAssignedChips:
                        if seatInfo.action in [ACTION_CALL, ACTION_RAISE]:
                            _server.trace("error, players who call or raise should have most chips in than anyone else in the game")
                            continue
                        else:
                            potChips = potChips + seatInfo.chipsIn
                            potSeats[seatId] = potSeats[seatId] + seatInfo.chipsIn
                            seatInfo.chipsIn = 0
                    else:
                        potChips = potChips + toBeAssignedChips
                        potSeats[seatId] = potSeats[seatId] + toBeAssignedChips
                        seatInfo.chipsIn = seatInfo.chipsIn - toBeAssignedChips                
                    
                    if seatInfo.action == ACTION_ALL_IN:
                        hasSomeoneAllIn = True
            
            if potChips > 0:
                pots.append([potChips] + potSeats)
                
                if hasSomeoneAllIn:
                    pots.append([])
    
    potVarList = []
    for potId, pot in enumerate(pots):        
        if len(pot) > 0:        
            potVar = "%".join([str(v) for v in pot])
            potVarList.append(RoomVariable("pot" + str(potId), potVar, True, True))
            
    return potVarList
    

def endGame(showdown = True):
    global pots, boardCards

    stopAllTasks()

    roomVarList = []
    roomVarList.append(RoomVariable("round", 0, True, True))
    roomVarList.append(RoomVariable("startchipin", "", True, True))
    
    if showdown:
        boardCardVar = "%".join([str(c) for c in boardCards])
    else:
        boardCardVar = ""
    roomVarList.append(RoomVariable("cards", boardCardVar, True, True))
    
    # assign pots
    assignPots()

    # when not in showdown, there is only one seat alive who wins the game
    onlyWinSeatId = -1
    for seatId, seatInfo in seats.iteritems():
        # return extra chips in to each player, there should be no extra chips in except when game is over
        if seatInfo.chipsIn > 0:
            # when player stand or quit, return the extra chips to his account
            if seatInfo.action == 0:
                if (seatInfo.oldUserId > -1) and (seatInfo.oldUserName != None):
                    user = TexasPlayer.get(seatInfo.oldUserName)
                    if user:
                        user.coin += seatInfo.chipsIn
                        user.experience += 5
                        user.put()
                        who = _server.getUserById(seatInfo.oldUserId)
                        response = ["updateCoinScore", str(user.coin),str(user.experience), str(user.winCount),str(user.attendCount)]
                        _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
            else:
                seatInfo.chips = seatInfo.chips + seatInfo.chipsIn

            seatInfo.chipsIn = 0
            
        # player who bets join showdown
        if (seatInfo.action not in [0, 2]):
            if showdown:
                hand = seatInfo.hand
                sevenCards = boardCards + [seatInfo.card1, seatInfo.card2]
                for card in [Card(c) for c in sevenCards]:
                    hand.add(card)
            else:
                onlyWinSeatId = seatId
                
        roomVarList.append(RoomVariable("seat" + str(seatId), seatInfo.getSeatVar(), True, True))
    
    expList = []
    potVarList = []
    for potId, pot in enumerate(pots):
        if len(pot) == 0:
            continue
    
        potChips = pot[0]
        potSeats = pot[1:]
            
        showdownPotSeats = []
        for seatId, seatChips in enumerate(potSeats):
            if seatChips > 0:
                if (not showdown) and (onlyWinSeatId == seatId):
                    showdownPotSeats.append(seatId)
                    break
                elif showdown:
                    if len(showdownPotSeats) == 0:
                        showdownPotSeats.append(seatId)
                    else:
                        bestHand = seats[showdownPotSeats[0]].hand
                        currentHand = seats[seatId].hand
                        if currentHand > bestHand:
                            showdownPotSeats = [seatId]
                        elif currentHand == bestHand:
                            showdownPotSeats.append(seatId)            
        
        #In addition to countless appear here, requiring the remaining chips to the next person to pick
        if len(showdownPotSeats) > 0:
            winChips = potChips / len(showdownPotSeats)
            for seatId in showdownPotSeats:
                # deal chips in pots to each winner
                seats[seatId].chips += winChips

                # mark the winners
                potSeats[seatId] = -potSeats[seatId]                    
                            
            potVar = "%".join([str(v) for v in ([potChips] + potSeats)])
            potVarList.append(RoomVariable("pot" + str(potId), potVar, True, True))
            
    playerCount = texasroomutils.room_player_count(_server)
    
    for seatId, seatInfo in seats.iteritems():
        addExp = 0
        if seatInfo.userId > -1:
            if seatId in showdownPotSeats :
                multiple = playerCount-2
                if multiple > 0 :
                    addExp = 2*multiple + 8
                else:
                    addExp = 8
            else :
                addExp = 5
            
            who = _server.getUserById(seatInfo.userId)
            if who :
                user = TexasPlayer.get(who.getName())
                if user:                
                    user.experience += addExp
                    user.coin += seatInfo.chips - seatInfo.sitChips
                    user.put()
                    seatInfo.sitChips = seatInfo.chips
                    response = ["updateCoinScore", str(user.coin),str(user.experience), str(user.winCount),str(user.attendCount)]
                    _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
            
        if (seatInfo.oldUserId > -1) and (seatInfo.oldUserName != None): 
            who = _server.getUserById(seatInfo.oldUserId)
            if who :
                user = TexasPlayer.get(who.getName())
                if user and who.getName() == seatInfo.oldUserName:
                    addExp = 5              
                    user.experience += addExp
                    user.coin += seatInfo.chips - seatInfo.sitChips
                    user.put()
                    response = ["updateCoinScore", str(user.coin),str(user.experience), str(user.winCount),str(user.attendCount)]
                    _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
            seatInfo.sitChips = 0
            seatInfo.chips = 0

        expList.append(str(addExp))
           
    expList.reverse()    
    roomVarList.extend(potVarList)
    roomVarList.append(RoomVariable("exp", "%".join(expList), True, True))    
    _server.setRoomVariables(_server.getCurrentRoom(), None, roomVarList)
    
    _server.trace("end game:")
    
    if playerCount > 1:
        waitSeconds = 5 + len(potVarList) * 3
        startGameStartTask(waitSeconds)


def limitByCoin(userId, type):   # coin limit
    global bigBlind
    
    user = TexasPlayer.get(userId)
    if not user:
        return -100
    
    data = {
        "B":bigBlind/2,
    }
    
    coin = user.coin
    
    if coin > data[type] :
        user.add_coins(-data[type])
        return 1
    else :
        return -1


def limitByCoinAndExp(userId, type):  # coin and level limit
    global bigBlind
    
    user = TexasPlayer.get(userId)
    if not user:
        return -100
    
    data = {
        "C":{ 'coin':bigBlind/2,'exp':0},
        "E":{ 'coin':bigBlind,'exp':0},
    }
    
    coin = user.coin
    experience = user.experience

    if coin < data[type]['coin']:
        return -1

    if experience < data[type]['exp']:
        return -2

    user.add_coins(-data[type]['coin'])

    return 1
