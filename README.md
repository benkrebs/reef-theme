# Reef Theme

A water theme for Home Assistant: frosted-glass cards, hairlines in the colours of the reef, and a background that shimmers like light under water.

| Reef Coral (light) | Reef Abyss (dark) |
| --- | --- |
| ![Reef Coral: the background shimmers like sunlight in a lagoon](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/coral-animated.webp) | ![Reef Abyss: bioluminescent plankton drifting in the deep sea](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/abyss-animated.webp) |
| ![Reef Coral dashboard](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/coral-dashboard.webp) | ![Reef Abyss dashboard](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/abyss-dashboard.webp) |
| ![Reef Coral more-info dialog](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/coral-dialog.webp) | ![Reef Abyss more-info dialog](https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/abyss-dialog.webp) |

<p align="center">
  <img src="https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/coral-mobile.webp" width="260" alt="Reef Coral on a phone">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/benkrebs/reef-theme/main/images/abyss-mobile.webp" width="260" alt="Reef Abyss on a phone">
</p>

## Themes

The file has three themes:

| Theme | Mode | Look |
| --- | --- | --- |
| **Reef** | Follows the light/dark setting of your profile or device | Reef Coral by day, Reef Abyss by night |
| **Reef Coral** | Always light | A sunlit coral reef: turquoise water, light shafts, caustics, corals on white sand |
| **Reef Abyss** | Always dark | The deep sea: almost black water, bioluminescent plankton and glowing neon tendrils |

## Features

- **Works with the built-in cards and pages.** The theme sets the classic variables and the newer `ha-color-*` design tokens, with a full primary palette. Tiles, badges, buttons, sliders, switches, dialogs, inputs, the sidebar, the header, and the settings pages all take on the theme.
- **Hairlines.** Cards, badges, sections, the header, dialogs and buttons get a 0.5 px line in the colour of the theme. Retina screens show it as a hairline, other screens round it up to 1 px.
- **Glass.** Cards, badges, the dashboard header, and dialogs are translucent, with a backdrop blur.
- **Animated background.** Caustics, light shafts, swaying corals, and drifting plankton. It is one self-contained SVG, built into the theme file: nothing to copy to `www/`, no external requests, no custom cards, no card-mod.
- **Thin and modern.** System fonts (Avenir Next, SF Pro, Segoe UI Variable, Roboto as fallback), round corners, quiet shadows.

<!-- ha-marketplace:exclude-start -->
## Installation

### Marketplace (Home Assistant 2026.11 and later) or HACS

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=benkrebs&repository=reef-theme&category=theme)

1. Select the badge, or open **Settings** > **Marketplace** (HACS before 2026.11) and add `https://github.com/benkrebs/reef-theme` as a custom repository of the type **Theme**.
2. Install **Reef Theme**. The Marketplace reloads the themes by itself.

### Manual

1. Copy [`themes/reef.yaml`](themes/reef.yaml) to `themes/reef/reef.yaml` in your configuration folder.
2. Run the `frontend.reload_themes` action, or restart Home Assistant.
<!-- ha-marketplace:exclude-end -->

## Use it

1. Make sure `configuration.yaml` loads the `themes` folder. Home Assistant adds this line when it creates the file, but older setups may lack it:

   ```yaml
   frontend:
     themes: !include_dir_merge_named themes
   ```

2. Open your **profile** and pick **Reef**, **Reef Coral**, or **Reef Abyss** under *Theme*. With **Reef**, the *Dark mode* setting next to it switches between the two looks.

You can also set the theme on one dashboard view only, with `theme: Reef Abyss` in the view configuration.

## Performance

The background animates with SVG (SMIL), drawn by the browser. Phones, tablets, and computers from the last years handle it without trouble. On a weak wall tablet, you can keep the glass and hairlines but give a single view a still background, which wins over the background of the theme:

```yaml
views:
  - title: Home
    background: "linear-gradient(180deg, #e4fafa, #85d6e0)"   # Reef Coral colours
    # background: "linear-gradient(180deg, #06243a, #01060e)" # Reef Abyss colours
```

## Customize

`themes/reef.yaml` is generated. To change colours, the background, or the strength of the glass, edit [`tools/build.py`](tools/build.py) and run:

```sh
python3 tools/build.py      # writes themes/reef.yaml and previews in assets/
python3 tools/validate.py --check-build   # checks the file like Home Assistant does (needs PyYAML)
```

The background previews are in [`assets/`](assets/): open them in a browser to see the animation.

## Compatibility

Tested with Home Assistant 2026.11. Older versions load the theme too; components that do not know a variable just ignore it.

## License

[MIT](LICENSE)
