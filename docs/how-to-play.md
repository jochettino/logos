# How to play

Logos is a logo-guessing game. You are shown an image that belongs to a company, brand or product, and you type its name.

## Rules

1. Press **Play** and choose a game: **Classic** (tech logos) or **18+** (adult logos). A random image is shown.
2. Type the name of the brand or product in the box and press **Guess**.
3. **Correct:** you score a point, and a new random image appears.
4. **Wrong:** the game is over. The correct answer is not revealed.
5. **Win:** if you name every image correctly, the game is over and you win.
6. An empty guess is ignored: the image stays the same and nothing is lost.
7. Press **Play again** (or go to the **Main menu** and choose **Play** again) to start over with a fresh shuffle.

## What counts as correct

- Upper and lower case do not matter: `java`, `Java` and `JAVA` are the same.
- Extra spaces around or inside your answer are ignored: `  java  ` is fine.
- Spelling must otherwise be exact. `Jvaa` is wrong.
- Some images accept more than one name (for example `Coke` as well as `Coca-Cola`). These alternatives are defined per image in the catalog (`app/catalog/*.yaml`).

## Score

The header shows `Score: X · Best: Y`: the correct answers in the current game and your best score across games in that mode. Both are stored in a cookie in your browser, so they are private to you and survive page reloads. Starting a new game keeps your best score.

## Images

- Every image is shown exactly once per game, in random order.
- A game therefore lasts at most as many rounds as there are images.
