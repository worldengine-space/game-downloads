# WorldEngine.space client

The desktop client has a local, packaged library interface and a separate sandboxed game surface. Android uses native Android views for its library and toolbar, with a persistent WebView for the game engines. The clients load the current ten-game catalog from WorldEngine.space.

## Interface

- Fixed viewport: all ten games fit at the default desktop size and at 960×600. Games occupy the remaining window height, with no page scrolling.
- Local desktop library, recent games, keyboard selection, native fullscreen, and a persistent account session.
- Native desktop download manager with progress, cancellation, SHA-256 verification, and Show in folder. Downloaded standalone installers are separate from the online client and keep their own local data.
- Account and wishlist dialogs preserve the running game. Per-game chat and game controls open on demand.
- Chat and Feed in the native toolbar expand a separate community surface without replacing the native library or reloading the game. General chat is open to guests; feed posting uses your account.
- Every catalog title uses the “- Recompiled” edition suffix.
- Android native library, landscape support, game touch controls, file picker, and system download manager. Hold a game tile to download its standalone APK.
- Internet required for the shared game library, accounts, cloud saves, and chat. Catalog metadata is cached locally; this is not an offline game installation manager or multiplayer game server.

The desktop interface uses Electron and a narrow IPC bridge available only to its packaged local renderer. Remote games have no Node.js access or native bridge. Only validated catalog download URLs are accepted by the download manager.

## Build

From the portal root, with the existing desktop and Android packaging dependencies installed:

```sh
node scripts/build-client-desktop.mjs windows
node scripts/build-client-desktop.mjs mac
node scripts/build-client-desktop.mjs linux
node scripts/build-client-android.mjs
```

Outputs and checksum metadata: `.build/client-downloads/`.

Windows: x64 portable EXE, launched directly. Mac: universal Intel/Apple Silicon PKG installs into Applications. Linux: x64 AppImage (mark executable before opening). Android: Android 8+ APK using the stable World Engine signing key. Desktop publisher signing and Apple notarization are not configured, so OS verification prompts apply. Native iPhone distribution still requires Apple Developer enrollment and signing; the portal offers a separate Safari Home Screen web app.

Client game integration is in `site/play/client-engine.css` and `window.WorldEngineClient` in the portal. Keep the frontend and this API backward compatible with installed clients. Rebuild desktop packages when changing the local client interface; library and game updates appear without reinstalling.

## Verification and release

`tests/client-native.cjs` checks the packaged desktop app over local CDP, all ten game surfaces, viewport sizing, recent games, and same-iframe account dialogs. Public release repository `worldengine-space/game-downloads` runs Windows, Linux and Android device checks in `client-verify.yml`. Android debugging is enabled only by an explicit ADB `smokeTest` launch extra.

Upload packages and SHA256SUMS to a draft release, verify them, then publish. `scripts/client-downloads.json` supplies the four platform links on `/play/`; `npm run build` validates the metadata and adds the links. Deploy with the existing Cloudflare Pages workflow. Never check in signing keys or passwords.
