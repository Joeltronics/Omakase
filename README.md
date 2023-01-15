# Omakase

An AI for playing Sushi Go.

Just a casual, for-fun project that I work on when I feel like it.

## How does it work?

There are different families of bots here, with each bot in the family building off the previous:

### Random

- `RandomAI` simply picks a random card from the hand. If it has chopsticks on its plate, there's a 50% chance it will use them in a given round.
- `RandomPlusAI` is similar, but with extra logic to skip certain obviously bad picks
	- e.g. it will not play an egg nigiri when a squid nigiri is available
- `RandomPlusPlusAI` will also automatically take a few hard-coded picks
	- e.g. if it has 2 sashimi, it will always choose a 3rd sashimi if it gets the chance

### Present Value

These determine the approximate point value of all cards in hand based on the current game state, and pick the one with the highest value.
They do not look ahead at future possible game states.

Point value is based on:

- Current points
	- e.g. a Nigiri is worth a specific amount of points right now
- Estimated average future points
	- e.g. a single Tempura is not worth any points, but if you get another one then the two together are worth 5 points, making a single Tempura worth 2.5 future points, multiplied by the probability you will see (and choose to take) another one later on
- How many points are blocking others
	- In a 2-player game, blocking the other player for 5 points is just as good as getting 5 points yourself
	- With more players, it's more complicated. Currently this is just based on an average of other players' scores, but in theory you should care more about blocking players close in score to you than players who are very ahead or behind.
- Opportunity cost of future moves
	- e.g. if you have a Wasabi on your plate, taking an egg nigiri may cost points relative to saving it for a squid or salmon nigiri

Bots in this family:

- `HandOnlyAI` only considers what cards it can play and how many cards are left
- `TunnelVisionAI` looks at its own hand & plate, but not any information from other players
- `BasicPresentValueAI` uses as much information as it can - it looks at known cards in other players' hands, and the known distribution of cards remaining in the deck
	- However, it still makes no assumptions about what other cards other players will _actually_ play - it essentially averages all of their possible plays
	- This bot is still incomplete - some cards are not implemented, and still use the tunnel vision logic

### Recursive AI

This AI looks ahead to all possible future game states.

Current limitations (all of which I would like to eventually improve):

- It does not work while there are still unknown cards
- Performance is not really optimized at all - it evaluates the _entire_ tree with no pruning
- It is only capable of looking ahead all the way to the end of the round, which makes it much too slow to look ahead when there are more than 4 or so cards left in each hand
- It makes very few assumptions about what cards others will actually play
	- Currently it's based on an average of all possible moves other players could play, aside from a few obvious bad picks

For the final round, its choice is based off of whatever results in the best average rank.

For earlier rounds, it uses the heuristic of the best average square-root difference in scores to each other player.
This is because we care more about differences against players who are close in score to us than players who are not.
This score also uses an estimate for the average final pudding scores based on the number of puddings at the end of this round.

## TODO

There are lots of TODO comments in the code, but some of the bigger ticket items:

- Add the ability to play against these bots
- Make a PyScript UI
- Finish PresentValueAI
	- It still falls back to TunnelVisionAI algorithm for a lot of cards
	- Better blocking logic (also up blocking weighting)
- Start making assumptions about what others will play
	- Use average weighted by likelihood, instead of just averaging all possibilities
	- Better guesses of blocking points
- Recursive AI that does not need to look ahead all the way to the end of the round
	- Essentially need an ability to score a given game state that's not at the end of a round
	- Many of the pieces for this are already there, but they need to be put together
- Improved estimates for blocking points
	- Account for _who_ you're blocking (e.g. use something similar to the sqrt-delta heuristic from the recursive solver)

## FAQ

**Can I play against it?**

Not yet - currently it can only play bots vs bots.

**Why not use minimax, alpha-beta pruning, etc?**

There are a few things that complicate this over a solver for a normal 2-player game:

- Players choose their cards simultaneously
- This supports more than 2 players
- There is imperfect information in the first few turns
- Chopsticks increase the number of possible moves pretty substantially

All of these are problems are solvable (or at least have "good enough" solutions), but they make it much more difficult.
I would like to get to this eventually, but since this is just a casual project, who knows if/when that will happen.

**Isn't minimax just as simple as taking the worst case from the recursive tree, which is already implemented?**

For 2 players, yes. For more, that depends on how exactly you define minimax for 3+ players.

Taking the worst case from the tree is effectively amounts to assuming we will always get blocked whenever possible - for example, this would likely cause the bot to rarely ever take Sashimi.
Essentially it's operating on the assumption that everyone is out to get you and will play whatever is worst for you, when it would be much better to assume they will play what is best for themselves (which may be the same, but may not).
In practice this is quite tricky, due to all the issues mentioned above.
