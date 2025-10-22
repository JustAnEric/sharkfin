<img src="https://github.com/snarkden/sharkfin/blob/main/assets/images/sharkfin.webp?raw=true" align="right" width="20%" height="20%">

# Sharkfin | Docs

> [!NOTE]
> This project was originally made by the [snarkden organization](https://github.com/snarkden). I have no affiliation with their projects, this is only a production-ready fork that is actively being maintained. This DOCS.md page is not made by members on the snarkden team.

## Local App Directory

The directory chosen by this project for Sharkfin is:

```cmd
C:\Users\<YOUR_USERNAME>\AppData\Local\sharkfin
```

Or, in simpler terms (just execute via Windows key):

```cmd
%localappdata%\sharkfin
```

## Loader Themes

Our loader themes are defined by a HTML page. In order to add your own loader theme, you may use this very basic template:

```cmd
| your-theme
| | config.json
| | style.css
| | window.html
```

Our loader themes are placed in this directory:

```cmd
C:\Users\<YOUR_USERNAME>\AppData\Local\sharkfin\loader-themes
```

**Note:** For more extensive customization, add the assets you need to load into the loader themes folder you create. For example, if you wanted to add VANTA for 3D animations, you'd include it in your directory like this:

```cmd
C:\Users\<YOUR_USERNAME>\AppData\Local\sharkfin\loader-themes\your-theme\VANTA.js
```

And import it into your `window.html` file like this:

```html
...
    ...
        <script src="./VANTA.js" defer></script>
    ...
...
```

`window.html`:

```html
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <div class="checkBg" style="position: fixed; top: 0; left: 0; --color1: #3b68b1; --color2: #3876b1; width: 100vw; height: 100vh; z-index: -1;"></div>

        <div style="display: grid; grid-template-columns: 320px 320px; height: 100vh; width: 100%; align-items: center; justify-content: center; text-align: center;">
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 18px;">
                <text style="font-size: 64px;">sharkfin</text><br>
                <text style="font-size: 22px;">by snarkden</text>
            </div>
        </div>

        <div id="progress"></div>
        <text id="status" style="font-size: 14px; position: fixed; bottom: 4px; left: 5px;">Loading...</text>
        <script>
            window.addEventListener("pywebviewready", function() {
                window.pywebview.api.doTasks();
            });
        </script>
    </body>
</html>
```

`style.css`:

```css
html, body {
    margin: 0;
    width: 100vw;
    height: 100vh;
    font-family: system-ui;
}

text {
    color: white;
}

#progress {
    position: fixed;
    bottom: 0;
    left: 0;
    background-color: #2e7ec8;
    height: 24px;
    width: 100%;
    transition: 500ms;
}

.checkBg {
    position: relative;
    background-color: gray;
    overflow: hidden;
}

.checkBg::before {
    content: "";
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: conic-gradient(
        var(--color1) 90deg,
        var(--color2) 90deg 180deg,
        var(--color1) 180deg 270deg,
        var(--color2) 270deg
    );
    background-repeat: repeat;
    background-size: 50px 50px;
    transform: rotate(30deg) translate3d(0, 0, 0);
    will-change: transform;
    animation: slide 15s linear infinite;
    backface-visibility: hidden;
}

@keyframes slide {
    from {
        transform: rotate(30deg) translate3d(0, 0, 0);
    }
    to {
        transform: rotate(30deg) translate3d(300px, 0, 0);
    }
}
```

`config.json`:

```json
{
    "title": "sharkfin",
    "width": 700,
    "height": 400,
    "debug": false,
    "loadingColor": "#FFFFFF"
}
```

The properties included in the `config.json` file are the defaults for Sharkfin to use.

## Modding Sharkfin

There is not an official library yet that can achieve sufficient modification of Sharkfin or Roblox. However, Sharkfin modifications will soon come out for this fork. There is no ET (estimated time) for the completion and release of this.
