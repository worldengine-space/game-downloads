"""Exercise exact signed release APKs on Android through the QA-only DevTools switch."""
import json, pathlib, subprocess, time, urllib.request, traceback
import websocket
from PIL import Image
out=pathlib.Path('android-evidence');out.mkdir(exist_ok=True)
def adb(*args,**kw): return subprocess.check_output(['adb',*args],**kw)
def attach(package):
    for _ in range(60):
        try:
            pid=adb('shell','pidof',package).decode().strip().split()[0]
            adb('forward','tcp:9222','localabstract:webview_devtools_remote_'+pid)
            pages=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
            page=next(p for p in pages if p.get('type')=='page')
            return websocket.create_connection(page['webSocketDebuggerUrl'],timeout=45,suppress_origin=True)
        except Exception: time.sleep(1)
    raise RuntimeError('WebView DevTools unavailable: '+package)
seq=0
def command(ws,method,params):
    global seq
    seq+=1;ws.send(json.dumps({'id':seq,'method':method,'params':params}))
    while True:
        response=json.loads(ws.recv())
        if response.get('id')==seq:
            if response.get('error') or response.get('result',{}).get('exceptionDetails'): raise RuntimeError(str(response))
            return response.get('result',{})
def evaluate(ws,expression):
    return command(ws,'Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True}).get('result',{}).get('value')
def wait_for(ws,expression,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=evaluate(ws,expression)
        if value:return value
        time.sleep(1)
    raise RuntimeError('Runtime condition timed out: '+expression)
def tap(ws,selector):
    q=json.dumps(selector)
    point=wait_for(ws,f"(()=>{{const b=document.querySelector({q});if(!b||b.disabled)return false;b.scrollIntoView({{block:'center'}});const r=b.getBoundingClientRect();return r.width&&r.height&&getComputedStyle(b).visibility!=='hidden'?{{x:r.x+r.width/2,y:r.y+r.height/2}}:false}})()")
    command(ws,'Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[point]})
    command(ws,'Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    time.sleep(1)
def screenshot(game):
    with (out/(game+'.png')).open('wb') as f:subprocess.run(['adb','exec-out','screencap','-p'],stdout=f,check=True)
def key(ws,code,keycode,key,seconds=0.1):
    command(ws,'Input.dispatchKeyEvent',{'type':'keyDown','code':code,'key':key,'windowsVirtualKeyCode':keycode,'nativeVirtualKeyCode':keycode})
    time.sleep(seconds)
    command(ws,'Input.dispatchKeyEvent',{'type':'keyUp','code':code,'key':key,'windowsVirtualKeyCode':keycode,'nativeVirtualKeyCode':keycode})
report=[]
files=sorted(pathlib.Path('apks').glob('*-android.apk'),key=lambda p:(p.stem not in ['revolt-android','destruction-derby-android'],p.name))
assert len(files)==10,f'Expected ten APKs, found {len(files)}'
for apk in files:
    game=apk.name.removesuffix('-android.apk');package='space.worldengine.recompiled.'+game.replace('-','');ws=None
    result={'id':game,'passed':False}
    try:
        adb('install','-r',str(apk));adb('logcat','-c')
        adb('shell','am','start','-n',package+'/space.worldengine.recompiled.MainActivity','--ez','smokeTest','true')
        ws=attach(package)
        evaluate(ws,"window.__qaErrors=[];window.addEventListener('error',e=>__qaErrors.push(e.message||('resource '+e.target.src)),true);window.addEventListener('unhandledrejection',e=>__qaErrors.push(String(e.reason)));true")
        time.sleep(8)
        if game=='revolt':
            wait_for(ws,"window.reconstruction?.ready && document.body.dataset.gameScreen==='title'",180)
            for selector in ['#game-start-race','#game-mode-single','#game-physics-0']:tap(ws,selector)
            wait_for(ws,"document.body.dataset.gameScreen==='name'")
            adb('shell','input','keyevent','66');time.sleep(1)
            for selector in ['#game-car-next','#game-track-next','#game-launch']:tap(ws,selector)
            wait_for(ws,"document.body.dataset.gameScreen==='race'")
            time.sleep(7)
            before=evaluate(ws,'[...window.reconstruction.vehicle.pose.position]')
            key(ws,'ArrowUp',38,'ArrowUp',5)
            after=evaluate(ws,'({position:[...window.reconstruction.vehicle.pose.position],phase:window.reconstruction.vehicle.state.phase})')
            distance=sum((a-b)**2 for a,b in zip(after['position'],before))**0.5
            assert after['phase']=='driving' and distance>10,{'before':before,'after':after,'distance':distance}
            result['driving']={'distance':distance,'phase':after['phase']}
        elif game=='destruction-derby':
            wait_for(ws,"document.querySelector('#start')&&!document.querySelector('#start').disabled",180)
            evaluate(ws,"document.querySelector('#mode').value='race';true")
            tap(ws,'#start');wait_for(ws,"document.body.classList.contains('playing')")
            time.sleep(20);key(ws,'Space',32,' ',8);key(ws,'End',35,'End',2)
        elif game in ['tom-jerry','tom-jerry-claymation']:
            tap(ws,'#start');wait_for(ws,"document.querySelector('#intro').hidden")
            key(ws,'KeyK',75,'k');key(ws,'KeyD',68,'d',3)
        elif game=='simfarm':
            tap(ws,'#launch-game');wait_for(ws,"document.querySelector('#launch-screen').hidden || getComputedStyle(document.querySelector('#launch-screen')).display==='none'")
            time.sleep(10);adb('shell','input','keyevent','66')
        elif game=='lemmings':tap(ws,'#menu button');time.sleep(8)
        else:
            wait_for(ws,"document.querySelector('canvas')")
            tap(ws,'canvas');adb('shell','input','keyevent','66');key(ws,'Space',32,' ');key(ws,'ArrowRight',39,'ArrowRight',3);time.sleep(8)
        result['runtime']=evaluate(ws,"({url:location.href,title:document.title,canvas:[...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,visible:!!c.getBoundingClientRect().width&&getComputedStyle(c).display!=='none'})),controls:document.querySelectorAll('#we-touch-controls button').length,bodyClass:document.body.className,screen:document.body.dataset.gameScreen,errors:__qaErrors})")
        assert any(c['visible'] and c['width']>0 for c in result['runtime']['canvas']),result['runtime']
        assert game=='simfarm' or result['runtime']['controls']>0,result['runtime']
        assert not result['runtime']['errors'],result['runtime']['errors']
        # Inspect actual Android compositor pixels, including WebGL canvases whose
        # drawing buffer is cleared between frames. Crop the middle of the canvas
        # to avoid counting touch controls, browser background or system bars.
        screenshot(game)
        bounds=evaluate(ws,"(()=>{const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight}})()")
        with Image.open(out/(game+'.png')) as frame:
            scale=frame.width/bounds['viewportWidth']
            inset=max(0,(frame.height-bounds['viewportHeight']*scale)/2)
            left=max(0,int((bounds['x']+bounds['width']*.25)*scale))
            top=max(0,int((bounds['y']+bounds['height']*.25)*scale+inset))
            right=min(frame.width,int((bounds['x']+bounds['width']*.75)*scale))
            bottom=min(frame.height,int((bounds['y']+bounds['height']*.75)*scale+inset))
            assert right>left and bottom>top,bounds
            colors=len(set(frame.crop((left,top,right,bottom)).convert('RGB').resize((64,40)).getdata()))
        assert colors>5,f'Android did not render a game frame: {colors} colors'
        result['frameColors']=colors
        evaluate(ws,"localStorage.setItem('__we_android_persistence_test','saved');true")
        ws.close();ws=None;adb('shell','am','force-stop',package)
        adb('shell','am','start','-n',package+'/space.worldengine.recompiled.MainActivity','--ez','smokeTest','true')
        ws=attach(package)
        assert evaluate(ws,"localStorage.getItem('__we_android_persistence_test')")=='saved'
        evaluate(ws,"localStorage.removeItem('__we_android_persistence_test');true");result['persistentStorage']=True
        logs=adb('logcat','-d','WorldEngineWeb:I','AndroidRuntime:E','*:S').decode(errors='replace')
        errors=[line for line in logs.splitlines() if 'WorldEngineWeb: ERROR:' in line or 'FATAL EXCEPTION' in line]
        assert not errors,errors
        result['passed']=True
    except Exception as error:
        result['failure']=str(error);traceback.print_exc();screenshot(game)
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
        (out/(game+'.log')).write_bytes(adb('logcat','-d','WorldEngineWeb:I','AndroidRuntime:E','*:S'))
        report.append(result);(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(result),flush=True)
        adb('uninstall',package)
assert all(r['passed'] for r in report),[r['id'] for r in report if not r['passed']]
