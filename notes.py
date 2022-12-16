

"""
Bad assumptions AI will make in first go:

1. Ignore chopsticks

This will make strategy (and number of permutations) more complicated. Better
to focus on basic strategy for now, though

2. Either ignore Pudding, or assume puddings count every round

Not sure what the best way to factor puddings into rounds 1&2 is.
Probably have to come up with some metric guessing likelihood of
pudding points at end of game

3. Maximize total number of points instead of relative to others

This one actually has an interesting effects:

3a. assume higher Maki count is always better, and (without Wasabi) higher
Nigiri is always better

Normally, you would assume it's always better to take a 3-Maki than a 1-Maki.
And that's almost always correct. However, there could be rare cases where
taking a smaller Maki could give last-place player a Maki advantage in order to
screw over 1st-place player.

Similarly, leaving a higher scoring Nigiri for someone else could cause them to
take that and leave you something more important (e.g. your 5th dumpling)
"""

"""
Other AI considerations:

1. Once implementing maximizing relative score, have to prioritize.

For example, do you aim for highest score relative to whoever's in 2nd, or to everyone?
If you're in last place, what do you prioritize? Whatever gets you the smallest margin
to 1st, or try to get 3rd place?

Best option might be "prioritize highest score relative to average of other players"

2. Other players may not play perfectly

This one's a little more complicated than it seems. For example, how are other players
prioritizing relative score?
"""


"""

Situations to test:

2-player:

* Hand A has 2 Sashimi, Hand B has 1 Sashimi

Technically it's possible to score Sashimi, but a good player could see that you
should never (*see below) take Sashimi - as soon as you do, the next turn it's
worth 9 relative points for the other player to block you

Note: it could still be worth it to play Sashimi if the other player has an option
worth more points than blocking you - but this is highly unlikely, as the only
other move worth 10 relative points is taking the last dumpling if both players
already have 4, and even then it's exactly equal (and I would think, if given an
otherwise equal choice, an AI would typically try to pick the one that maxes
absolute score, which would be the dumplings). This could also make a good test
case!


* Hand A has 3 Sashimi, hand B has none

Again, it's (probably) never worth it to score Sashimi, as you can always get blocked


* Hand A has 2 Sashimi, Hand B has 2 Sashimi

I think it's probably worth it to play Sashimi here because the other player can't
possibly block you, but I need to actually sit down and to the logic to confirm this 


* Hand A has 3 Sashimi, Hand B has 1 Sashimi

I suspect here it's worth it to take Sashimi with one hand but not the other, but
again, I need to actually logic this out
"""




"""
Figuring out total possible number of combinations:

This is just a generalization. It assumes two very incorrect things:
1. all cards are unique (fixing assumption makes state way smaller)
2. ignore chopsticks (fixing assumption makes state way larger)



The formula:

(c!)^p

c: number of cards per player
p: number of players



Derivation of formula:

3 players, 3 (unique) cards each

P1: A B c
P2: D E F
P3: G H I

P1 has 3 options
P2 has 3 options
P3 has 3 options

That's 3^3 = 27 combinations

For each combo, now we're at:
P1: A B
P2: D E
P3: G H

2^3 = 8 combinations

Total:
(Adding *1^3 term)
3^3 * 2^3 = 216

So (3*2)^3 = (3*2*1)^3 = (3!)^3



Total combinations:

5 players, 7 cards: (7!)^5 = 5,040^5        = 3.3e18
4 players, 8 cards: (8!)^4 = 40,320^4       = 2.6e18
3 players, 9 cards: (9!)^3 = 362,880^3      = 4.8e16
2 players, 10 cards: (10!)^2 = 3,628,800^2 = 1.3e13 = 13,000 Giga-combinations

That's a lot...




Combinations with fewer cards left:

3 players
1: (1!)^3 = 1
2: (2!)^3 = 8
3: (3!)^3 = 216
4: (4!)^3 = 13824
5: (5!)^3 = 1,728,000
6: (6!)^3 = 373,248,000 = 0.4 Giga
7: (7!)^3 = 128,024,064,000 = 128 Giga
8 & 9: don't know the full game state yet!

4 players
1: (1!)^4 = 1
2: (2!)^4 = 16
3: (3!)^4 = 1,296
4: (4!)^4 = 331,776
5: (5!)^4 = 207,360,000 = 0.2 Giga
6-8: don't know full state

5 players:
1: (1!)^5 = 1
2: (2!)^5 = 32
3: (3!)^5 = 7,776
4-7: don't know full state

2 players
...
8: (8!)^2 = 1,625,702,400 = 1 Giga
9: (9!)^2 = 131,681,894,400 = 131 Giga
10: don't know full state


1 Gigacombination:
if it takes 100 CPU cycles to determine a combination,
On a 1 GHz processor it will take 100 seconds to resolve all
"""