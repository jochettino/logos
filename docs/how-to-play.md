# How to play

Logos is a logo-guessing game. You are shown an image that belongs to a company, brand or product, and you type its name.

## Rules

1. When you open the game, a random image is shown.
2. Type the name of the brand or product in the box and press **Guess**.
3. **Correct:** you score a point, and a new random image appears.
4. **Wrong:** you score nothing. The correct answer is revealed and a new random image appears. There is no second try on the same image.
5. An empty guess is ignored: it does not count as an attempt and the image stays the same.

## What counts as correct

- Upper and lower case do not matter: `java`, `Java` and `JAVA` are the same.
- Extra spaces around or inside your answer are ignored: `  java  ` is fine.
- Spelling must otherwise be exact. `Jvaa` is wrong.
- Some images accept more than one name (for example `Coke` as well as `Coca-Cola`). These alternatives are defined per image in `app/images.json`.

## Score

The header shows `Score: X / Y`: correct answers out of total attempts. Your score is stored in a cookie in your browser, so it is private to you and survives page reloads. **Reset score** clears it.

## Images

- Every image is shown once before any image repeats. After the last one, the cycle starts again.
- The game is endless.
