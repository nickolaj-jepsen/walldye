import { describe, expect, it } from 'vitest';
import { namedColours, pickAccent, seedsFromText } from '../../src/lib/import-theme';
import type { Hex } from '../../src/lib/theme';

const MOCHA = { bg: '#1E1E2E', fg: '#CDD6F4' };
// Catppuccin Mocha's ANSI 1-6; blue is the most colourful of them.
const BLUE = '#89B4FA';

describe('seedsFromText', () => {
  it('reads a theme token and three colours as before', () => {
    expect(seedsFromText(' nord ')).toEqual({ bg: '#2E3440', fg: '#ECEFF4', accent: '#88C0D0' });
    expect(seedsFromText('#111, #eee, #f80')).toEqual({
      bg: '#111111',
      fg: '#EEEEEE',
      accent: '#FF8800',
    });
  });

  it('reads kitty', () => {
    const kitty = `# vim:ft=kitty
foreground              #CDD6F4
background              #1E1E2E
selection_foreground    #1E1E2E
selection_background    #F5E0DC
cursor                  #F5E0DC
active_tab_background   #CBA6F7
color0 #45475A
color8 #585B70
color1 #F38BA8
color9 #F38BA8
color2  #A6E3A1
color3  #F9E2AF
color4  #89B4FA
color5  #F5C2E7
color6  #94E2D5
color7  #BAC2DE`;
    expect(seedsFromText(kitty)).toEqual({ ...MOCHA, accent: BLUE });
  });

  it('reads Ghostty, with bare hex values and the palette lines', () => {
    const ghostty = `palette = 0=#45475a
palette = 1=#f38ba8
palette = 2=#a6e3a1
palette = 3=#f9e2af
palette = 4=#89b4fa
palette = 5=#f5c2e7
palette = 6=#94e2d5
background = 1e1e2e
foreground = cdd6f4
cursor-color = f5e0dc
selection-background = 353749`;
    expect(seedsFromText(ghostty)).toEqual({ ...MOCHA, accent: BLUE });
  });

  it('reads Alacritty TOML, skipping the bright, cursor and selection sections', () => {
    const toml = `[colors.primary]
background = "#1E1E2E"
foreground = "#CDD6F4"

[colors.selection]
background = "#F5E0DC"
text = "#1E1E2E"

[colors.bright]
blue = "#FF0000"

[colors.normal]
black = "#45475A"
red = "#F38BA8"
green = "#A6E3A1"
yellow = "#F9E2AF"
blue = "#89B4FA"
magenta = "#F5C2E7"
cyan = "#94E2D5"`;
    expect(seedsFromText(toml)).toEqual({ ...MOCHA, accent: BLUE });
  });

  it('reads Alacritty YAML by indentation', () => {
    const yaml = `colors:
  selection:
    background: '#FFFFFF'
  primary:
    background: '#1E1E2E'
    foreground: '#CDD6F4'
  bright:
    blue: '#FF0000'
  normal:
    red: '#F38BA8'
    blue: '#89B4FA'`;
    expect(seedsFromText(yaml)).toEqual({ ...MOCHA, accent: BLUE });
  });

  it('reads Windows Terminal JSON, foot, WezTerm and Xresources', () => {
    const json = `{
  "name": "Catppuccin Mocha",
  "background": "#1E1E2E",
  "foreground": "#CDD6F4",
  "selectionBackground": "#585B70",
  "red": "#F38BA8",
  "blue": "#89B4FA",
  "brightBlue": "#FF0000",
  "purple": "#F5C2E7"
}`;
    const foot = `[colors]
foreground=cdd6f4
background=1e1e2e
regular1=f38ba8
regular4=89b4fa
bright4=ff0000`;
    const wezterm = `[colors]
foreground = "#CDD6F4"
background = "#1E1E2E"
ansi = [
  "#45475A", "#F38BA8", "#A6E3A1", "#F9E2AF",
  "#89B4FA", "#F5C2E7", "#94E2D5", "#BAC2DE",
]
brights = ["#FF0000", "#FF0000"]`;
    const xresources = `! Catppuccin
*.foreground:  #CDD6F4
*.background:  #1E1E2E
*.cursorColor: #F5E0DC
*.color1:      #F38BA8
*.color4:      #89B4FA`;
    for (const text of [json, foot, wezterm, xresources]) {
      expect(seedsFromText(text)).toEqual({ ...MOCHA, accent: BLUE });
    }
  });

  it('reads base16 YAML: base00, base05 and an accent from base08 to base0E', () => {
    const base16 = `scheme: "Gruvbox dark"
base00: "282828" # ----
base05: "d5c4a1" # -
base08: "fb4934" # red
base09: "fe8019" # orange
base0D: "83a598" # blue`;
    expect(seedsFromText(base16)).toEqual({ bg: '#282828', fg: '#D5C4A1', accent: '#FE8019' });
  });

  it('takes an accent the file names outright', () => {
    expect(
      seedsFromText('bg: "#101010"\nfg: "#E0E0E0"\naccent: "#00FF88"\ncolor1: #FF0000'),
    ).toEqual({ bg: '#101010', fg: '#E0E0E0', accent: '#00FF88' });
  });

  it('is null without a background, a foreground or an accent', () => {
    expect(seedsFromText('')).toBeNull();
    expect(seedsFromText('hello there')).toBeNull();
    expect(seedsFromText('background #000000\ncolor1 #FF0000')).toBeNull();
    expect(seedsFromText('background #000000\nforeground #FFFFFF')).toBeNull();
  });
});

describe('namedColours', () => {
  it('keeps the first of a name and ignores keyless hex values', () => {
    const named = namedColours('#FF0000\nbackground #111111\nbackground #222222');
    expect([...named]).toEqual([['background', '#111111']]);
  });
});

describe('pickAccent', () => {
  const bg = '#1E1E2E' as Hex;
  it('picks the most colourful candidate that stands out from the ground', () => {
    expect(pickAccent(['#45475A', '#F38BA8', '#89B4FA'] as Hex[], bg)).toBe('#89B4FA');
    expect(pickAccent(['#330000', '#89B4FA'] as Hex[], bg)).toBe('#89B4FA');
  });

  it('falls back to the most contrast when none stands out, and to undefined with none', () => {
    expect(pickAccent(['#2A2A3A', '#303048'] as Hex[], bg)).toBe('#303048');
    expect(pickAccent([], bg)).toBeUndefined();
  });
});
