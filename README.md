# Print & Cut Flashcards (Anki add-on)

Pulls a deck out of Anki and opens it in the print-and-cut layout page in your
browser, with the cards loaded and the preview already built.

## Install

1. In Anki: **Tools → Add-ons → Install from file…**
2. Select `print_cut_flashcards.ankiaddon`.
3. Restart Anki.

Requires Anki 2.1.50 or later.

## Use

1. **Tools → Print & Cut Flashcards…**
2. Pick a deck (subdecks are included) and which fields are the front and back.
3. Optionally edit the label, which defaults to the deck name, and choose the
   corner it prints in on every card's back.
4. Click **Open print layout**. The page opens in your default browser.
5. On the page, set paper, grid, text size and mirroring, add any per-card
   labels, then print with scale at 100% and headers and footers off.

The page is written to this add-on's `user_files` folder, which Anki keeps
when the add-on is updated.

## Limits

- It reads raw note fields rather than the rendered card, so it suits
  Front/Back-style notes best. Cloze deletions are shown with the answer
  filled in.
- The field dropdowns are filled from a sample of the deck's notes, so a rare
  note type in a very large deck may not appear there. Its notes are still
  included if they have fields with the chosen names.
- Audio and images aren't printed.
