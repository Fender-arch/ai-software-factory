# Mini App — Experience Layer (маскот)

Слот интервью-компаньона в `apps/miniapp/`. Контракты Discovery/API не меняются.

## Спокойный режим

- Кнопка **«Спокойный режим»** на home и в шапке workspace.
- Сохраняется в `localStorage` (`asf-calm-mode=1`).
- `prefers-reduced-motion: reduce` тоже замораживает маскота и foundry-фон; текст статуса остаётся.

## События (клиентская шина)

`idle` · `listening` · `thinking` · `got_answer` · `got_voice` · `got_file` · `draft_ready` · `error`

Эмитит `app.js` из уже существующих действий (отправка, голос, файл, черновик ТЗ, ошибка). Не серверный event bus.

## Маскот UNI4IT

По умолчанию в слоте — робот-единорог (`brand/mascot-bust.png`): белый корпус, лавандовые грива/рог, headset, **ASF** на груди. Реакции интервью — CSS (`idle` дыхание, `listening` пульс, `thinking` наклон, `got_*` подпрыгивание). Rive по-прежнему опционален.

Логотип и цвета: `apps/miniapp/brand/` и `docs/17-Brand-Assets.md`.

## Опциональный Rive

1. Положите файл **`apps/miniapp/mascot.riv`** рядом с `index.html` (тот же URL: `/miniapp/mascot.riv`).
2. В Rive Editor заведите state machine с именем **`Mascot`**.
3. Имена trigger/boolean inputs — как события выше (`idle`, `listening`, …). Опционально boolean `calm`.
4. Обновите Mini App (Telegram кэширует WebApp — полностью закройте и откройте).

Если имя машины другое:

```html
<meta name="asf-mascot-riv" content="./mascot.riv" />
<meta name="asf-mascot-sm" content="YourStateMachine" />
```

или до скриптов: `window.ASF_MASCOT = { src: "./mascot.riv", stateMachine: "YourStateMachine" }`.

Рантайм: `@rive-app/canvas@2.31.2` с jsDelivr, запасной unpkg. Если `.riv` нет, CDN не грузится — остаётся PNG-единорожка. Это нормально для Telegram WebView.

**Не в этом слайсе:** lip-sync / TTS-рот маскота.

Лицензия ассета: свой бренд-файл. Публичные community `.riv` подключайте только с явной лицензией автора.
