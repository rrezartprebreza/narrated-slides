# User guide

This guide is for people using Narrated Slides. If you are the one who installed it, see the
[README](../README.md) first.

## 1. Open the app

Go to **http://localhost:8000** (or the port your administrator chose). The pill at the top right should say **Ready**.
If it is red, open it for fix hints, or see [Troubleshooting](TROUBLESHOOTING.md).

## 2. Add a deck

Pick one of three ways:

| Way | When to use it |
|---|---|
| **Drop a `.pptx`** on the big box (or click to browse) | You already have a PowerPoint deck. Save `.ppt` or Keynote files as PowerPoint first. |
| **Try the sample deck** | You want to see how it works in ten seconds. It has notes on four slides and none on the fifth, on purpose. |
| **Generate one from an idea** | You have a topic but no slides. Needs the optional Presenton service. |

Hidden slides are left out of the video. Your recent decks appear at the bottom of the home page, so you can come back to them.

## 3. Write the script

Each slide is read aloud from its **speaker notes**.

- Click a slide in the left strip. Its notes appear under the preview. Type to edit; changes are saved automatically
  (see "All changes saved" at the top).
- **Preview voice** plays the current slide so you can hear how it sounds.
- **Write with AI** drafts notes for the current slide. **Write missing notes** does it for every empty slide.
  This needs the optional notes model; if it is not set up, the button opens the Services panel to show you how.
  Always read AI drafts before exporting.
- A slide with **no notes** stays silent for a few seconds (you choose how long in the next step).
- The title above the slide is editable. Click it to rename the deck.

**Writing tips**

- Write the way you speak. Short sentences sound better than long ones.
- Aim for three or four sentences per slide.
- Spell out numbers and abbreviations the way they should sound ("twenty twenty-six", "C B K").
- Use punctuation for pacing: a comma is a short pause, a full stop is a longer one.

**Shortcuts:** `Alt` + `↑` / `↓` changes slide. `Ctrl`/`⌘` + `Enter` previews the voice.

## 4. Voice and export

Press **Voice & export** (top right, or step 3 in the header).

- **Voice**: grouped by language. Pick one and press **Hear it** for a sample line. For Albanian decks pick a **Shqip** voice.
  The same picker is also at the top of the script page, so **Preview voice** uses it too.
- **Speaking speed**: 1.0× is natural. 0.9× to 1.1× is the comfortable range.
- **Pause after each slide**: breathing room before the next slide appears.
- **Silent slide length**: how long slides without notes stay on screen.
- **Video size**: 1080p for sharing, 720p for smaller files and faster exports.
- **My voice**: narrate in your own voice. Press **My voice** next to the voice list, then **Record** and read the
  sample text aloud for 10 to 20 seconds in a quiet room (or upload a clip of clean English speech). Listen back, give it
  a name, tick the permission box and save. It appears under **My voices** in every voice picker. Cloned voices speak
  English and take longer to export than the built-in voices. Only clone your own voice or one you have permission for.
  If the button says the add-on isn't started, ask whoever installed the app to run `docker compose --profile clone up -d --build`.
- **Subtitles**: tick any of English, Shqip, Italiano, Português, Norsk and Türkçe. The narration's own language (marked
  *original*) is always included. The other languages are translated by the notes AI, so it must be set up (see Services).
  Each language becomes a subtitle track inside the MP4 (pick it in VLC, QuickTime or the page's player) and an SRT file
  in **Subtitles, all languages (ZIP)** for YouTube or your LMS. Machine translation can be wrong, so check important wording.

The summary shows how many slides will be narrated and the estimated length. Press **Create narrated video** and watch
the progress. When it finishes you can play the video in the page and download:

| File | What it is |
|---|---|
| **Narrated video (MP4)** | The finished video. Plays everywhere. |
| **Subtitles (SRT)** | Sentence-by-sentence captions. Upload next to the video on YouTube, Vimeo, LMS platforms, or load into VLC. |
| **Audio per slide (ZIP)** | One MP3 per narrated slide, for use in other editors. |
| **Deck with notes (PPTX)** | Your original deck with the notes you wrote put back into it. Keep this as your master copy. |

## 5. Change something later

- **Different wording or voice:** go back to the script or the settings, change it, and press **Create narrated video** again.
- **Change how a slide looks:** edit the deck in PowerPoint (start from **Deck with notes** so your script comes along),
  save it, and upload it again. The app is not a slide designer on purpose; PowerPoint and Keynote are better at that.
- **Your settings are remembered** in your browser.

## 6. Your files and privacy

Everything stays on the computer running Docker. Uploaded decks and finished videos are deleted automatically after
7 days (the administrator can change that). Use the trash icon on a recent deck to delete it right away.

## Frequently asked questions

**Why does my slide look slightly different from PowerPoint?**
Slides are drawn with LibreOffice. Common fonts are included, but unusual fonts or advanced effects may differ. Check the
preview before exporting; if it is wrong, simplify the slide or use common fonts.

**Can it read Albanian slides?**
Yes. Pick a voice under **Shqip (Albanian)** (on the script page or in Voice & export) and write the notes in Albanian.
**Write with AI** also writes in the slide's language. Spell out numbers and abbreviations the way they should sound.

**Other languages?**
Only if a voice exists for that language. Kokoro covers several; more can be added as Piper voices (see Configuration).

**Do animations or transitions survive?**
No. Each slide becomes one still picture in the video.

**How long does it take?**
It depends on your computer: speech is generated on the CPU. Try the sample deck to see how long it takes for you. The first export is slower because the voice model warms up.
