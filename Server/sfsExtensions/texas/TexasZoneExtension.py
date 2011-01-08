#-*- coding: utf-8 -*-
#
# Simple Python Extension
# v 1.0.0
#
import it.gotoandplay.smartfoxserver.exceptions as __exceptions
import it.gotoandplay.smartfoxserver.lib.SmartFoxLib as __smartFoxLib
import it.gotoandplay.smartfoxserver.lib as __lib
import it.gotoandplay.smartfoxserver.data as __data
import it.gotoandplay.smartfoxserver.db as __db
import it.gotoandplay.smartfoxserver.crypto as __crypto
import it.gotoandplay.smartfoxserver.extensions as __extensions

import java
import types
import random
import org.json as __json
from HandEvaluator import makeRequest
from java.util import ArrayList, HashMap, LinkedList

from texaslib.db import Model
from texaslib.models.texasplayer import TexasPlayer

def init():
    global db
    global _appurl
    global currentUserList

    Model.db = db = _server.getDatabaseManager()    
    _appurl = ''
    currentUserList = []
    _server.trace("Python texas zone extension starting")
    
def destroy():
    global db

    del db

    _server.trace("Python texas zone extension stopping")
    
def escapeQuotes(txt):
    res = __smartFoxLib.escapeQuotes(txt)
    
    return str(res)
    
def handleRequest(cmd, params, who, roomId, protocol):
    if (cmd == "getRoomUsers") and (protocol == _server.PROTOCOL_STR):    
        queryRoomId = int(params[0])
        
        response = {}
        response["users"] = []    
        response["_cmd"] = cmd
        response["r"] = queryRoomId
        
        room = _server.getCurrentZone().getRoom(queryRoomId)
        if not room == None:
            userList = room.getAllUsers()
            
            for user in userList:
                if (not user.getVariable("n") == None) and (not user.getVariable("t") == None) \
                and (not user.getVariable("c") == None) and (not user.getVariable("s") == None) \
                and (not user.getVariable("Kcoin") == None):
                    
                    userObj = {}
                    userObj["n"] = user.getVariable("n").getValue()
                    userObj["t"] = user.getVariable("t").getValue()
                    userObj["c"] = user.getVariable("c").getValue()
                    userObj["s"] = user.getVariable("s").getValue()
                    userObj["zs"] = user.getVariable("zs").getValue()
                    userObj["sl"] = user.getVariable("sl").getValue()
                    userObj["Kcoin"] = user.getVariable("Kcoin").getValue()
                
                    if (not userObj["n"] == None) and (not userObj["t"] == None) \
                    and (not userObj["c"] == None) and (not userObj["s"] == None) \
                    and (not userObj["Kcoin"] == None):
                        response["users"].append(userObj)
                    
            if len(response["users"]) > 0:
                _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_JSON)

        
    elif(cmd == "sendGift") and (protocol == _server.PROTOCOL_STR):
        global _appurl,currentUserList
        url = _appurl + 'get_api/'
        values = {}
        values['method'] = 'User.send_goods'
        values['uid'] = params[0]
        values['sessionid'] = params[1]
        values['name'] = params[2]
        values['money_type'] = params[3]
        values['num'] = int(params[4])
        values['toId'] = params[5]
        
        result = makeRequest(url,values)
        if result != None:
            if int(result['return_code'])==0:
                response = [cmd, str(result['return_code']),str(params[4]), str(params[5]), result['data']['userName']]
                newId = -1
                for i in currentUserList:
                    if i["uname"] == str(params[5]):
                        newId = i["uid"]
                toUser = _server.getUserById(newId)
                _server.sendResponse(response, -1, None, [who,toUser], _server.PROTOCOL_STR)
            else :
                response = [cmd, str(result['return_code']),result['data']['msg']]
                _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
        else:
            response = {}
            response["_cmd"] = "sendGiftKO"
            response["err"] = "E0000"
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)


    elif (cmd == "useItem") and (protocol == _server.PROTOCOL_STR):
        global _appurl
        seatId = int(params[4])
        url = _appurl + 'get_api/'
        values = {}
        values['sessionid'] = params[5]
        values['method'] = 'User.use_goods'
        values['uid'] = params[0]
        values['name'] = params[1]
        values['category'] = params[2]
        values['num'] = int(params[3])
        result = makeRequest(url,values)
        if result and seatId >=-1 and seatId <= 8 :
            response = [cmd, str(result['return_code'])]
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)

            room = _server.getCurrentZone().getRoom(roomId)
            userList = room.getAllUsers()
            response = ['zsUpdateOK',str(result['data']['itemId']),str(seatId)]
            _server.sendResponse(response, -1, None, userList, _server.PROTOCOL_STR)
        else:
            response = {}
            response["_cmd"] = "zsUpdateKO"
            response["err"] = "E0000"
            _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_STR)
    
    elif (cmd == "getMyMsgs") and (protocol == _server.PROTOCOL_STR):
        clientMaxMsgId = int(params[0])
    
        messages, maxMsgId = getMessageListByUserId(who.getName(), clientMaxMsgId)    
        
        response = {}
        response["_cmd"] = cmd
        response["msgs"] = messages
        response["maxId"] = maxMsgId
        
        _server.sendResponse(response, -1, None, [who], _server.PROTOCOL_JSON)
    
    elif(cmd == "invitePlayer") and (protocol == _server.PROTOCOL_STR):
        global currentUserList
        inviter = TexasPlayer.get(who.getName())
        if not inviter:
            return
        invite_player_id = None
        for i in currentUserList:
            if i["uname"] == str(params[0]):
                invite_player_id = i["uid"]
        invite_player = _server.getUserById(invite_player_id)
        if not invite_player:
            return
        response = {}
        response["_cmd"] = cmd
        response["inviter_id"] = who.getUserId()
        response["inviter_uid"] = who.getName()
        response["inviter_name"] = inviter.userName
        response["inviter_icon"] = inviter.userIcon
        response["inviter_host"] = params[1]
        response["inviter_port"] = params[2]
        response["inviter_zone"] = params[3]
        response["inviter_room"] = params[4]
        _server.sendResponse(response, -1, None, [invite_player], _server.PROTOCOL_JSON)


def handleInternalEvent(evt):    
    global _appurl
    evtName = evt.getEventName()
    
    if evtName == "loginRequest":
        handleLoginRequest(evt)
    
    elif (evtName == "userExit") or (evtName == "userLost") or (evtName == "logOut"):
        who = evt.getObject("user")        
        post_data = {"userId":who.getName()}
        makeRequest(_appurl+"set_user_outline/", post_data)
        
def handleLoginRequest(evt):
    global _appurl,currentUserList

    nick = evt.getParam("nick")
    chan = evt.getObject("chan")
    word = evt.getParam("pass").split('_')
    
    pwd = word[0]
    _appurl = word[3]
           
    _server.trace("Login Request: " + nick + "&&" + pwd)
    
    key = _server.getSecretKey(chan)
    md5Pass = _server.md5(key + "23njkcdp9u8")
        
    response = {}
        
    if nick and (pwd == md5Pass):
        cZone = _server.getCurrentZone()
        
        oldUser = cZone.getUserByName(nick);
        if not oldUser == None:
            _server.logoutUser(oldUser);
    
        try:
            #newUser = _server.loginUser(nick, pwd, chan)
            newUser = _server._sfs.canLogin(nick, pwd, chan, _server.getCurrentZone().getName(), True)
        except __exceptions.LoginException, exc:
            response["_cmd"] = "logKO"
            response["err"] = exc.getMessage()
        else:        

            url = _appurl + 'get_api/'
            values = {}
            values['uid'] = nick
            values['method'] = 'User.userInfo'
            values['sessionid'] = word[2]
            result = makeRequest(url,values)
            
            if result != None:
                userInfo = result['data']
                response["_cmd"] = "logOK"
                response["uid"] = newUser.getUserId()
                response["uname"] = newUser.getName()
                response["coin"] = userInfo["coin"]
                response["nick"] = userInfo["userName"]
                response["icon"] = userInfo["userIcon"]
                response["F_coin"] = userInfo["F_coin"]
                response["decoration"] = userInfo["decoration"]
                response["experience"] = userInfo["experience"]
                response["winCount"] = userInfo["winCount"]
                response["attendCount"] = userInfo["attendCount"]
                for i in currentUserList:
                    if i["uname"] == newUser.getName():
                        currentUserList.remove(i)
                currentUserList.append(response)
            else:
                response["_cmd"] = "logKO"
                response["err"] = "E0000"
                
    else:
        response["_cmd"] = "logKO"
        response["err"] = "username password wrong"
            
    _server.sendResponse(response, -1, None, chan, _server.PROTOCOL_JSON)
    
  
def getMessageListByUserId(userId, maxMsgId):
    global db
    
    sql = "SELECT * FROM message WHERE toUserId = '%s' AND messageId > %s ORDER BY messageId DESC LIMIT 50" % (str(userId), str(maxMsgId))
    queryRes = db.executeQuery(sql)
    
    messages = []
    if (queryRes != None) and (queryRes.size() > 0):
        maxMsgId = queryRes.get(0).getItem("messageId")
    
        for row in queryRes:
            msgObj = {}
            msgObj["typ"] = int(row.getItem("messageType"))
            msgObj["ct"] = str(row.getItem("createTime"))
            msgObj["p1"] = str(row.getItem("param1"))
            msgObj["p2"] = str(row.getItem("param2"))
            msgObj["number"] = str(row.getItem("number")) 
            messages.append(msgObj)
            
    return messages, maxMsgId
