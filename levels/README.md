# Level files

Each `.txt` file in this folder is one level. They are played in file-name order.

```
name: Forest Edge
theme: green
subtitle: Where every journey begins
sign: Text for the first ? sign on the map
sign: Text for the second ? sign
---
<map rows>
```

Header keys: `name`, `theme` (`green`, `yellow`, `golden`, `autumn`, `dusk`),
`subtitle` (optional), `music` (optional, default `forest`), and one `sign:` line per `?`
on the map, in order from left to right. Lines starting with `;` are comments.

Every character in the map is one 16x16 tile. The screen shows 30 x 17 tiles.
Rows of different lengths are padded with empty space.

## Legend

| Char | Meaning |
|------|---------|
| ` ` `.` | empty |
| `#` | grassy earth (auto-tiled edges) |
| `R` | rocky earth (auto-tiled) |
| `S` | mossy stone bricks |
| `=` | wooden plank (one-way: jump up through, Down+Jump to drop) |
| `_` | rope-bridge deck (one-way) |
| `~` | water (hazard: costs a heart, returns you to safe ground) |
| `^` | spikes (hazard) |
| `P` | player start (exactly one) |
| `E` | exit door |
| `L` | locked exit door (needs a `k` key somewhere in the level) |
| `C` | checkpoint lamp |
| `?` | sign (text from the `sign:` lines) |
| `M` | moving log. Each `-` to its right = 1 tile of horizontal travel; each `:` below it = 1 tile of vertical travel |
| `F` | crumbling plank (a run of `F`s makes one plank) |
| `o` | coin |
| `h` | health potion |
| `k` | key |
| `G` | secret gem (max one per level) |
| `c` | treasure chest (5 coins) |
| `s` `b` `z` | snail, boar, bee |
| `T` `t` `y` | big / medium / small tree (colour follows the theme) |
| `u` | bush · `m` small mushroom · `n` big mushroom · `f` fence · `r` rock · `w` flowers · `i` fern |

Objects, enemies and decoration stand on the tile **below** their cell, so put them in the
row directly above the ground.

Open space under 3 or more tiles of solid ground (with a floor below it) automatically gets a
dark rock back wall, so tunnels and caves look enclosed. Water is drawn behind the terrain, so
let it touch the pool walls.

## Jump limits (for designing)

- Single jump: about **3 tiles** up, **4 tiles** across
- Double jump: about **6 tiles** up, **7 tiles** across
- A dash adds about **3 tiles** of horizontal reach (one air dash per jump)
- The hero is about 2 tiles tall, so tunnels must be at least **3 tiles** high

After editing, run `python tools/level_tool.py check` and `python tools/level_tool.py preview`.
