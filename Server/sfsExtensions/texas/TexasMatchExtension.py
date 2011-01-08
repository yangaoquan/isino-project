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
from texaslib.db import Model
from HandEvaluator import makeRequest
from texaslib.models.texasplayer import TexasPlayer
from texaslib.texasutils import texasroomutils

importPath = os.path.abspath("sfsExtensions/texas")
if not (importPath in sys.path):
    sys.path.append(importPath)

from HandEvaluator import *

ACTION_OUT_GAME, ACTION_START, ACTION_FOLD, ACTION_CHECK, ACTION_CALL, ACTION_RAISE, ACTION_ALL_IN = range(7)

class SeatInfo:
    def __init__(self, seatId):
        self.seatId = seatId
        self.userId = -1
        self.uid = -1
        self.action = ACTION_OUT_GAME
        self.chips = 0
        self.sitChips = 0
        self.chipsIn = 0
        self.card1 = -1
        self.card2 = -1
        self.hand = Hand()
        self.oldUserId = -1
        self.outUid = -1
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
            str(self.hand.ranks[0]), str(self.hand.ranks[1]), str(self.hand.ranks[2]), str(self.hand.ranks[3]), str(self.hand.ranks[4]), str(self.outUid)])
        return "%d%%%d%%%d%%%d%%%d" % (self.userId, self.action, self.chips, self.chipsIn, self.outUid)
        
    def userSit(self, userId, sitChips, uid):
        global waitUserActionTask, bigBlind, sessionid, appurl,winSeats
        global isGame, startPeople, startBlind, addBlind, addBlindRate, cRoom, seats
        playerCount = texasroomutils.room_player_count(_server)
        self.userId = userId
        self.uid = uid
        self.action = ACTION_OUT_GAME
        self.chips = sitChips
        self.sitChips = sitChips
        
        self.updateSeatVar()

        self.timeoutCount = 0
        
        # when game is not start, check whether need to start game
        round = texasroomutils.room_round(_server)
        if (round == 0) and (playerCount == startPeople) and (waitUserActionTask == None):
            isGame = 1
            threeSeatId = -1
            threeWinChips = -1
            bigBlind = startBlind
            addBlind = startBlind * addBlindRate
            winSeats = {}
            userList = cRoom.getAllUsers()
            _server.sendResponse(["ttGameStart","OK"], -1, None, userList, _server.PROTOCOL_STR)
            
            subChips = -(serverCoin + joinCoin)
            for seatId, seatInfo in seats.iteritems():
                if seatInfo.userId > -1 : 
                    user = _server.getUserById(int(seatInfo.userId))
                    if user :
                        player = TexasPlayer.get(user.getName())
                        if player:                
                            player.coin += subChips
                            player.put()
                    
            startGameStartTask(5)
        
    def userStand(self, who = None):
        global cZone, cRoom, bigBlind ,startPeople,assignRate
        global serverCoin, joinCoin, abideCount, isGame,threeSeatId, threeWinChips
        hasLeftRoom = True
        if who == None:
            hasLeftRoom = False
            who = _server.getUserById(self.userId)
        
        if (not hasLeftRoom) and (who != None):
            _server._helper.switchPlayer(who, cRoom.getId(), True) 
               
        playerCount = texasroomutils.room_player_count(_server)
            
        userInfo = TexasPlayer.get(who.getName())
        if userInfo != None:
            if isGame :
                if self.experience == 0 :
                    self.experience = 5
                userList = cRoom.getAllUsers()
                if playerCount >= 3 :
                    winChips = 0
                    userInfo.coin += winChips
                    userInfo.attendCount += 1
                    userInfo.experience += self.experience
                    res = ["out", "-1", str(self.seatId), str(winChips), cRoom.getName()]
                    _server.sendResponse(res, -1, None, userList, _server.PROTOCOL_STR)
                else:
                    if playerCount == 0 :
                        winChips = joinCoin * startPeople * assignRate[0]
                    if playerCount == 1 :
                        firstSeatId = firstWinChips = -1 
                        winChips = joinCoin * startPeople * assignRate[1]
                        for seatId, seatInfo in seats.iteritems():
                            if seatInfo.seatId != self.seatId and seatInfo.userId > -1:
                                firstSeatId = seatInfo.seatId
                                firstWinChips = joinCoin * startPeople * assignRate[0]
                                seatInfo.userStand()
                                
                        res = ["result", "1", str(firstSeatId), str(firstWinChips), str(2), str(self.seatId), str(winChips), str(3), str(threeSeatId), str(threeWinChips), cRoom.getName()]
                        _server.sendResponse(res, -1, None, userList, _server.PROTOCOL_STR)
                    if playerCount == 2 :
                        winChips = joinCoin * startPeople * assignRate[2]
                        res = ["out", "3", str(self.seatId), str(winChips), cRoom.getName()]
                        _server.sendResponse(res, -1, None, userList, _server.PROTOCOL_STR)
                        threeWinChips = winChips
                        threeSeatId = self.seatId
                
                    userInfo.coin += winChips
                    userInfo.winCount += 1
                    userInfo.attendCount += 1
                    userInfo.experience += self.experience
                    
                userInfo.put()
                
            response = ["updateCoinScore", str(userInfo.coin),str(userInfo.experience), str(userInfo.winCount),str(userInfo.attendCount)]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
            
        else:
            _server.trace("serverError, user delete game")
        
        self.experience = 0    
        self.chips = 0
        self.sitChips = 0
   
        # game is not started
        round = texasroomutils.room_round(_server)
        if round == 0:
            if isGame :
                if (playerCount < 2):
                    self.outUid = -1
                else:
                    self.outUid = self.userId
            self.userId = -1
            self.action = ACTION_OUT_GAME
            
            self.updateSeatVar()
            
            # stop the timer which is about to start the game            
            if (playerCount < 2):
                stopAllTasks()
            if (playerCount < 1):
                if isGame : 
                    isGame = 0
                    for seatId, seatInfo in seats.iteritems():
                        seatInfo.reset()
                        seatInfo.updateSeatVar()
            
        else:
            if self.action != ACTION_OUT_GAME:
                self.oldUserId = self.userId
                if who != None:
                    self.oldUserName = who.getName()
            
            if isGame :
                if (playerCount < 2):
                    self.outUid = -1
                else:
                    self.outUid = self.userId
            self.userId = -1
            self.action = ACTION_OUT_GAME
            
            self.updateSeatVar()
            
            if checkWaitChipInTaskRunning(self.seatId):
                # stand when task is waiting me to chipin
                stopAllTasks()
                
                if not checkGameOrRoundOver():                
                    beginNextChipIn(self.seatId)
            elif (not checkGameOrRoundOver()) and (self.timeoutCount >= abideCount-1):
                beginNextChipIn(self.seatId)
        
        # notify client when auto kick out of the game from server
        if (self.timeoutCount >= abideCount) and (who != None):
            response = ["forceStand"]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
                
        self.timeoutCount = 0

        if (not hasLeftRoom) and (who != None) and (not who.isSpectator()):
            _server.joinRoom(who, cRoom.getId(), True, cZone.getAutoJoinRoom())
        
    def reset(self):        
        self.userId = -1
        self.uid = -1
        self.action = 0
        self.chips = 0
        self.sitChips = 0
        self.chipsIn = 0
        self.card1 = -1
        self.card2 = -1
        self.hand = Hand()
        self.oldUserId = -1
        self.outUid = -1
        self.oldUserName = None
        self.timeoutCount = 0
        self.experience = 0 
    def updateSeatVar(self):
        global cRoom
        
        seatVar = RoomVariable("seat" + str(self.seatId), self.getSeatVar(), True, True)
        _server.setRoomVariables(cRoom, None, [seatVar])
        
class WaitUserActionTaskHandler(__scheduling.ITaskHandler):    
    def doTask(self, task):
        global waitUserActionTask,abideCount
    
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
                
                if (chipInSeatInfo.timeoutCount >= abideCount):                
                    chipInSeatInfo.userStand()
                    return
                
            doFoldAction(chipInSeatId)

def init():
    _server.trace("Python texas room extension starting")
    
    global cZone
    global cRoom
    
    global bigBlindSeatId
    global smallBlindSeatId
    global pots
    global boardCards
    
    global addBlindRate    #  0.5
    global assignRate      #  (0.5,0.3,0.2)
    global startPeople     #  9
    global abideCount      #  3
    global takeCoin        #  1000
    global isGame
    global threeSeatId
    global threeWinChips
    global sessionid
    global appurl
    global winSeats

    global seats
    global cards
    
    global joinCoin
    global serverCoin
    global bigBlind
    global addBlind
    global startBlind
    
    global minChipIn
    global maxChipIn    
    
    global scheduler
    global waitUserActionTaskHandler
    global waitUserActionTask
    
    cZone = _server.getCurrentZone()
    cRoom = _server.getCurrentRoom()
    Model.db = _server.getDatabaseManager()
   
    maxChipIn = 0
 
    bigBlindSeatId = 0
    smallBlindSeatId = 0
    pots = []
    boardCards = []

    isGame = 0
    abideCount = 3
    startPeople = 9
    takeCoin = 1000
    assignRate = (0.5,0.3,0.2)
    addBlindRate = 0.5
    threeSeatId = -1
    threeWinChips = -1
    winSeats = {}
    
    # init 9 seats
    seats = dict([(seatId, SeatInfo(seatId)) for seatId in range(9)])
    
    # init all 52 cards
    cards = range(52)

    startBlind = int(cRoom.getName().split("_")[1])
    addBlind = bigBlind = startBlind
    serverCoin = int(cRoom.getName().split("_")[2])
    joinCoin = serverCoin * 10    
    
    scheduler = __scheduling.Scheduler()
    scheduler.startService()
    
    waitUserActionTaskHandler = WaitUserActionTaskHandler()
    waitUserActionTask = None
    
def destroy():
    global cZone, cRoom, scheduler

    del cZone
    del cRoom
    
    del sys.modules["HandEvaluator"]
    
    scheduler.destroy(None)

    _server.trace("Python texas room extension stopping")
    
    
def handleRequest(cmd, params, who, roomId, protocol):
    global bigBlind,maxChipIn, cZone ,cRoom, sessionid, appurl
    global serverCoin, joinCoin ,abideCount,startPeople,takeCoin,assignRate,addBlindRate, isGame
    if (cmd == "sit") and (protocol == _server.PROTOCOL_STR):
        seatId = int(params[0])
        buyInChips = serverCoin + joinCoin
        
        sessionid = str(params[1])
        appurl = str(params[2])

        if isGame == 0 :
            url = appurl + 'get_api/'
            values = {}
            values['sessionid'] = sessionid
            values['method'] = 'User.init_texas'

            result = makeRequest(url,values)
            if result != None:
                data = result['data']['init_competition']
                abideCount = data['abideCount']
                startPeople = data['startPeople']
                takeCoin = data['takeCoin']
                addBlindRate = data['addBlindRate']
                assignRate = data['assignRate']
        
        
        if (seatId < 0) or (seatId >=9):
            return
        
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
            
            seatInfo.userSit(who.getUserId(), takeCoin, who.getName())
            
    elif (cmd == "stand") and (protocol == _server.PROTOCOL_STR):
        seatId = int(params[0])
        uid = who.getUserId()
        
        if (seatId < 0) or (seatId >= 9):
            return
        else:
            seatInfo = seats[seatId]
            if (seatInfo.userId == uid):
            
                seatInfo.userStand()                

    elif(cmd == "gameStatus") and (protocol == _server.PROTOCOL_STR):

        response = {}
        response["_cmd"] = cmd
        response["isGame"] = isGame
        _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_JSON)

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
            cRoom = _server.getCurrentRoom() 
            _server._helper.dispatchPublicMessage(face, cRoom, who)
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
    global seats, serverCoin, joinCoin, takeCoin, cZone

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
        buyInChips = serverCoin + joinCoin
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
            elif coin < buyInChips:
                response = ["sitKO", "E0019"]
            else:
                sitSuccess = False
                for seatId, seatInfo in seats.iteritems():
                    if seats[seatId].userId == -1:                                     
                        seatInfo.userSit(user.getUserId(), takeCoin, user.getName())
                        sitSuccess = True
                        break      
                        
                if not sitSuccess:
                    response = ["sitKO", "E0020"]
                    
            if not response == None:
                _server._helper.switchPlayer(user, room.getId(), True)            
                
                if not user.isSpectator():
                    _server.joinRoom(user, room.getId(), True, cZone.getAutoJoinRoom())
                    
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
    global cZone, cRoom, bigBlindSeatId, smallBlindSeatId, bigBlind, cards, boardCards, minChipIn, maxChipIn, pots, isGame ,winSeats
    
    round = texasroomutils.room_round(_server)
    if round > 0:
        _server.trace("unhandled error, game already started")
        return
    
    # check out of chips user
    leaveSeat = []
    leaveCount = 0
    for seatId, seatInfo in seats.iteritems():    
        # auto stand when user is out of chips
        if (seatInfo.userId > -1) and (seatInfo.chips == 0):
            leaveSeat.append(seatInfo)
        if (seatInfo.userId > -1) and (seatInfo.chips > 0):
            leaveCount += 1
          
    if leaveCount >= 3 or len(leaveSeat) == 1:
        for user in leaveSeat :
            user.userStand()
    else :
        standlist = winSeats.keys()
        standlist.sort()
        standlist.reverse()
        for i in standlist:
            tempUser = seats[winSeats[i][0]]
            if (tempUser.userId > -1) and (tempUser.chips == 0):
                tempUser.userStand()
                
    playerCount = texasroomutils.room_player_count(_server)
    if playerCount < 2:
        _server.trace("not enought user to start the game")
        return
    
    _server.trace("Room %d: game start" % (cRoom.getId()))
    round = 1
    
    # shuffle cards
    random.shuffle(cards)
    nextCardIndex = 0
    roomVarList = []
    
    # update seatInfo to playing status, assign hole cards to each player
    for seatId, seatInfo in seats.iteritems():
        if seatInfo.userId > -1:
            seatInfo.action = 1            
            seatInfo.chipsIn = 0
            seatInfo.hand = Hand()
            seatInfo.oldUserId = -1
            seatInfo.oldUserName = None
            
            seatInfo.card1 = cards[nextCardIndex]
            seatInfo.card2 = cards[nextCardIndex + 1]        
            nextCardIndex = nextCardIndex + 2
            
            # deal hand cards to each player
            response = ["preflop", str(seatInfo.card1), str(seatInfo.card2)]                
            who = _server.getUserById(int(seatInfo.userId))            
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)

        else:
            if isGame == 0 :            
                seatInfo.reset()
            
    # update dealer index
    dealerSeatId = getNextSeatIdInPlaying(texasroomutils.room_dealer(_server))            
            
    # init board cards
    boardCards = cards[nextCardIndex:nextCardIndex+5]
    
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
    _server.setRoomVariables(cRoom, None, roomVarList)
    
    if not checkGameOrRoundOver():        
        beginNextChipIn(bigBlindSeatId)

    
# return the next in game seatId who is closest to the currentSeatId on a clockwise direction        
def getNextSeatIdInPlaying(currentSeatId):
    nextSeatId = (currentSeatId + 1) % 9
    # 0: not in game or just quit game
    # 2: fold
    # 6: all-in
    while seats[nextSeatId].action in [0, 2, 6]:
        nextSeatId = (nextSeatId + 1) % 9
        if nextSeatId == currentSeatId:
            if seats[nextSeatId].action in [0, 2, 6]:
                return None
            else:
                return nextSeatId
                
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
    global minChipIn, maxChipIn, cRoom
    
    stopAllTasks()
    
    nextChipInSeatId = getNextSeatIdInPlaying(seatId)
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
        _server.setRoomVariables(cRoom, None, [RoomVariable("startchipin", chipinStr, True, True)])
            
        # start wait chipin timer
        startWaitChipInTask(nextChipInSeatId)        
            
    else:
        _server.trace("error, where must be more than one player who is not quit, fold or all-in when begin next chipin")
        
def beginNextRound():
    global boardCards, cRoom, minChipIn, bigBlind, pots, seats
    
    stopAllTasks()
    
    round = texasroomutils.room_round(_server)
    round = round + 1
    
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
        
    _server.setRoomVariables(cRoom, None, roomVarList)
    
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
    global cRoom, pots, boardCards, isGame, bigBlind, addBlind, winSeats

    stopAllTasks()
    
    roomVarList = []
    roomVarList.append(RoomVariable("round", 0, True, True))
    roomVarList.append(RoomVariable("startchipin", "", True, True))
    
    if showdown:
        boardCardVar = "%".join([str(boardCards[0]), str(boardCards[1]), str(boardCards[2]), str(boardCards[3]), str(boardCards[4])])
    else:
        boardCardVar = ""
    roomVarList.append(RoomVariable("cards", boardCardVar, True, True))
    
    # assign pots
    assignPots()
    winPot = ''
    # when not in showdown, there is only one seat alive who wins the game
    onlyWinSeatId = -1
    for seatId, seatInfo in seats.iteritems():
        if seatInfo.chipsIn > 0:
            if seatInfo.action != 0:
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
        tempPotSeats = potSeats
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
            
    winSeats = {}
    while_index = 0
    tmp_potSeats = range(len(tempPotSeats))
    while len(tmp_potSeats) > 1 and while_index < 9:
        while_index += 1
        WinPotSeats = []
        removeList = []
        for seatId in tmp_potSeats:
            if tempPotSeats[seatId] > 0:
                if (not showdown) and (onlyWinSeatId == seatId):
                    WinPotSeats.append(seatId)
                    break
                elif showdown:
                    if len(WinPotSeats) == 0:
                        WinPotSeats.append(seatId)
                    else:
                        bestHand = seats[WinPotSeats[0]].hand
                        currentHand = seats[seatId].hand
                        if currentHand > bestHand:
                            WinPotSeats = [seatId]
                        elif currentHand == bestHand and seatId not in WinPotSeats:
                            WinPotSeats.append(seatId)
            else:
                removeList.append(seatId)
        for seatId in removeList :
            tmp_potSeats.remove(seatId)
        WinPotSeats.sort()
        for seatId in WinPotSeats:
            tmp_potSeats.remove(seatId)
            winSeats[len(winSeats.keys())+1] = [seatId]
    
    if tmp_potSeats:
        winSeats[len(winSeats.keys())+1] = tmp_potSeats    
        
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
        if (seatInfo.oldUserId > -1) and (seatInfo.oldUserName != None):
            addExp = 5
        seatInfo.experience += addExp
        expList.append(str(addExp)) 
                
    expList.reverse()
           
    roomVarList.extend(potVarList)
    roomVarList.append(RoomVariable("exp", "%".join(expList), True, True))    
    _server.setRoomVariables(cRoom, None, roomVarList)
    
    _server.trace("end game:")
    
    if playerCount > 1:
        isGame += 1
        bigBlind += addBlind
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
