import json,os,subprocess,time,urllib.request,xml.etree.ElementTree as ET
import websocket
os.makedirs('client-android-results',exist_ok=True)
def adb(*args):return subprocess.check_output(['adb',*args],text=True).strip()
def tap_label(label):
 for _ in range(45):
  adb('shell','uiautomator','dump','/sdcard/client-ui.xml');xml=adb('shell','cat','/sdcard/client-ui.xml')
  root=ET.fromstring(xml)
  for n in root.iter('node'):
   if label in (n.get('text',''),n.get('content-desc','')):
    import re
    x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')));adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));return
  time.sleep(1)
 raise Exception('Missing native control: '+label)
def shot(name):
 with open('client-android-results/'+name+'.png','wb') as f:subprocess.run(['adb','exec-out','screencap','-p'],stdout=f,check=True)
adb('logcat','-c');adb('install','-r','dist/WorldEngine-Android.apk');adb('shell','am','start','-n','space.worldengine.client/.MainActivity','--ez','smokeTest','true');time.sleep(12)
for attempt in range(40):
 adb('shell','uiautomator','dump','/sdcard/client-ui.xml');xml=adb('shell','cat','/sdcard/client-ui.xml')
 if 'SimFarm - Recomplied' in xml:break
 time.sleep(1)
open('client-android-results/library.xml','w').write(xml)
open('client-android-results/logcat.txt','w').write(adb('logcat','-d'))
shot('library')
expected=['SimFarm - Recomplied','Tom & Jerry - Recomplied','Golden Axe - Recomplied','Arkanoid - Recomplied','Lemmings - Recomplied','Prince of Persia - Recomplied','Tyrian - Recomplied','Re-Volt - Recomplied','Destruction Derby - Recomplied']
root=ET.fromstring(xml)
for title in expected:assert any(n.get('content-desc')==title for n in root.iter('node')),title
shot('library');tap_label('SimFarm - Recomplied');time.sleep(15)
pid=adb('shell','pidof','space.worldengine.client');adb('forward','tcp:9223','localabstract:webview_devtools_remote_'+pid)
pages=json.load(urllib.request.urlopen('http://127.0.0.1:9223/json'));page=next(p for p in pages if p['url'].startswith('https://worldengine.space/play'));ws=websocket.create_connection(page['webSocketDebuggerUrl'],suppress_origin=True);seq=0
def evaluate(expression):
 global seq
 seq+=1;ws.send(json.dumps({'id':seq,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}}))
 while True:
  msg=json.loads(ws.recv())
  if msg.get('id')==seq:
   if 'exceptionDetails' in msg.get('result',{}):raise Exception(msg)
   return msg['result']['result'].get('value')
results=[]
for game in ['simfarm','tom-jerry','tom-jerry-claymation','golden-axe','arkanoid','lemmings','prince-of-persia','tyrian','revolt','destruction-derby']:
 evaluate('window.WorldEngineClient.launch('+json.dumps(game)+')');time.sleep(9)
 result=evaluate('({game:window.WorldEngineClient.state().game,height:innerHeight,scroll:document.documentElement.scrollHeight,stage:document.getElementById("game-stage").clientHeight,loaded:!!document.querySelector("iframe")?.contentDocument?.body.children.length})')
 assert result['game']==game and result['loaded'] and result['scroll']<=result['height']+1 and result['stage']>=result['height']-55,result
 results.append(result)
 if game=='simfarm':
  evaluate('window.__qaFrame=document.querySelector("iframe");window.WorldEngineClient.account()');time.sleep(2);assert evaluate('document.getElementById("account-dialog").open&&window.__qaFrame===document.querySelector("iframe")');evaluate('document.getElementById("account-dialog").close()')
shot('game');open('client-android-results/result.json','w').write(json.dumps(results,indent=2));ws.close()
