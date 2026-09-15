"""Exercise signed release APKs on an Android emulator via their QA-only DevTools switch."""
import json, pathlib, subprocess, time, urllib.request
import websocket
out=pathlib.Path('android-evidence');out.mkdir(exist_ok=True)
def adb(*args,**kw): return subprocess.check_output(['adb',*args],**kw)
def attach(package):
    for _ in range(40):
        try:
            pid=adb('shell','pidof',package).decode().strip().split()[0]
            adb('forward','tcp:9222','localabstract:webview_devtools_remote_'+pid)
            pages=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
            page=next(p for p in pages if p.get('type')=='page')
            return websocket.create_connection(page['webSocketDebuggerUrl'],timeout=30,suppress_origin=True)
        except Exception: time.sleep(1)
    raise RuntimeError('WebView DevTools did not become available: '+package)
seq=0
def evaluate(ws,expression):
    global seq
    seq+=1
    ws.send(json.dumps({'id':seq,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}}))
    while True:
        response=json.loads(ws.recv())
        if response.get('id')==seq:
            if response.get('result',{}).get('exceptionDetails'): raise RuntimeError(str(response))
            return response.get('result',{}).get('result',{}).get('value')
report=[]
files=sorted(pathlib.Path('apks').glob('*-android.apk'),key=lambda p:(p.stem not in ['revolt-android','destruction-derby-android'],p.name))
assert len(files)==10, f'Expected ten APKs, found {len(files)}'
for apk in files:
    game=apk.name.removesuffix('-android.apk');package='space.worldengine.recompiled.'+game.replace('-','')
    adb('install','-r',str(apk));adb('logcat','-c')
    adb('shell','am','start','-n',package+'/space.worldengine.recompiled.MainActivity','--ez','smokeTest','true')
    ws=attach(package)
    evaluate(ws,"window.__qaErrors=[];window.addEventListener('error',e=>__qaErrors.push(e.message||('resource '+e.target.src)),true);window.addEventListener('unhandledrejection',e=>__qaErrors.push(String(e.reason)));true")
    time.sleep(25)
    before=evaluate(ws,"({url:location.href,title:document.title,canvas:document.querySelectorAll('canvas').length,controls:document.querySelectorAll('#we-touch-controls button').length,errors:__qaErrors})")
    assert before['url'].startswith('https://appassets.androidplatform.net/assets/'),before
    assert before['canvas']>0,before
    if game!='simfarm': assert before['controls']>0,before
    # Actual Android input goes through the WebView to start menus and exercise movement.
    for key in [66,62,66,19,22,21]:
        adb('shell','input','keyevent',str(key));time.sleep(1)
    time.sleep(8)
    with (out/(game+'.png')).open('wb') as f: subprocess.run(['adb','exec-out','screencap','-p'],stdout=f,check=True)
    errors=evaluate(ws,'__qaErrors')
    # Check the isolated stable origin keeps progress across process death.
    evaluate(ws,"localStorage.setItem('__we_android_persistence_test','saved');true")
    ws.close();adb('shell','am','force-stop',package)
    adb('shell','am','start','-n',package+'/space.worldengine.recompiled.MainActivity','--ez','smokeTest','true')
    ws=attach(package)
    assert evaluate(ws,"localStorage.getItem('__we_android_persistence_test')")=='saved'
    evaluate(ws,"localStorage.removeItem('__we_android_persistence_test');true");ws.close()
    (out/(game+'.log')).write_bytes(adb('logcat','-d','WorldEngineWeb:I','AndroidRuntime:E','*:S'))
    report.append({'id':game,'startup':before,'errors':errors,'persistentStorage':True})
    (out/'report.json').write_text(json.dumps(report,indent=2))
    assert not errors, f'{game}: {errors}'
    adb('uninstall',package)
