# Demo images for photo input

Three phone-style photos for testing photo input and for the video. They're ours (generated), so they can be public.

| File | What | What it should give |
|---|---|---|
| `handwritten-list.jpg` | A handwritten order on lined paper, in Finnish and English: "Tilaus maanantaiksi / 10 kg voita / 20 l laktoositon maito / 5 kg mozzarella / 2 laatikkoa kananmunia ✓ / gluten-free flour 10 kg" | An order for Monday with 5 lines. "2 laatikkoa" (2 cases) of eggs should be asked about or converted |
| `chalkboard-menu.jpg` | A chalkboard: "TODAY / Salmon soup / Reindeer stew / Blueberry pie", with "~60 guests" in the corner | A menu for about 60 guests, so a cart with assumptions |
| `whiteboard-ideas.jpg` | A messy whiteboard: "Gluten-free pizza night!", Margherita and Funghi on a GF base, "? Pepperoni (check GF!)", dessert crossed out, "~40 guests Friday" | A menu for 40 on Friday. Gluten-free should hold, and the crossed-out dessert should be left out |

**How they were made.** On Sun 15 Nov 2026, with the Gemini API image model `gemini-3-pro-image`
(`generateContent`, `responseModalities: ["IMAGE"]`, aspect ratio 3:4), one call per image. The nano-banana MCP
tool's model (`gemini-2.5-flash-image-preview`) is no longer served, so the API was called directly. Every image was
checked by eye, and all the text is spelled exactly as prompted. Prompts:

```python
P = {
"handwritten-list": """A realistic smartphone photo, taken from above at a slight angle, of a handwritten shopping list on a sheet of lined notepad paper lying on a stainless steel restaurant kitchen counter. Natural uneven kitchen lighting, a soft shadow from the phone, slight blur at one edge, a little crease in the paper. Written in blue ballpoint pen in quick, casual but legible handwriting, one item per line, spelled exactly like this:
Tilaus maanantaiksi
10 kg voita
20 l laktoositon maito
5 kg mozzarella
2 laatikkoa kananmunia
gluten-free flour 10 kg
A small tick mark next to the eggs line. The edge of a cutting board and a pen are visible at the border. No other text.""",
"chalkboard-menu": """A realistic smartphone photo of a restaurant chalkboard menu board hanging on a wooden wall, taken handheld at a slight angle with natural window light and a little glare on the board. Hand-lettered in white and coloured chalk, slightly smudged, spelled exactly like this:
TODAY
Salmon soup
Reindeer stew
Blueberry pie
and in the top right corner, smaller: ~60 guests
Chalk dust at the bottom edge of the board. No other text.""",
"whiteboard-ideas": """A realistic smartphone photo of a messy office whiteboard in a restaurant back room, taken handheld at a slight angle with fluorescent light reflections. Brainstorm notes in black, blue and red marker, quick handwriting, some arrows and circles, one item crossed out. Spelled exactly like this:
Gluten-free pizza night!
Margherita - GF base, mozzarella, basil
Funghi - mushrooms, GF base
Pepperoni (check GF!)
Dessert: ice cream?
~40 guests Friday
"Pepperoni" has a red question mark. A magnet and a dry-erase marker sit on the tray. No other text.""",
}
```
