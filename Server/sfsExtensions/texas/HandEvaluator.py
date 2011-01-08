#
# Simple Python Extension
# v 1.0.0
#

TWO, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE, TEN, JACK, QUEEN, KING, ACE = range(13)

DIAMONDS, HEARTS, CLUBS, SPADES = range(4)

RANK_ABBR = '23456789TJQKA'
SUIT_ABBR = 'dhcs'

RANK_NAME = ['two','three','four','five','six','seven','eight','nine','ten','jack','queen','king','ace']

SUIT_NAME = ['diamonds','hearts','clubs','spades']

HIGHCARD, PAIR, TWOPAIR, SET, STRAIGHT, FLUSH, FULLHOUSE, QUADS, STRAIGHTFLUSH, SUPERSTRAIGHTFLUSH = range(10)

TYPE_NAMES = {
    HIGHCARD:      'HIGHCARD',
    PAIR:          'PAIR',
    TWOPAIR:       'TWOPAIR',
    SET:           'SET',
    STRAIGHT:      'STRAIGHT',
    FLUSH:         'FLUSH',
    FULLHOUSE:     'FULLHOUSE',
    QUADS:         'QUADS',
    STRAIGHTFLUSH: 'STRAIGHTFLUSH',
    SUPERSTRAIGHTFLUSH: 'SUPERSTRAIGHTFLUSH',
}

def _pluralize_rank(r_str):
	if r_str == 'six': 
		return r_str + 'es'
	return r_str + 's'

class Hand(object):   

	def __init__(self):
		self.cards = []
		self.dirty = False
		self.type = HIGHCARD
		self.ranks = []
		self.desc = ''

	def add(self, card):
		self.cards.append(card)
		self.dirty = True

	def get_type(self):
		if not self.dirty:
			return self.type
		self._analyze()
		return self.type

	def __cmp__(self, other):
		type = self.get_type()
		other_type = other.get_type()
		n = cmp(type, other_type)
		if n != 0:
			return n
		if self.ranks == other.ranks:
			return 0
		if self.ranks < other.ranks:
			return -1
		return 1

	# determine the best hand possible given the current set of cards
	def _analyze(self):
		self.dirty = False
		if len(self.cards) < 5:
			return
		r2c = {}
		s2c = {}
		for c in self.cards:
			r2c.setdefault(c.rank, []).append(c)
		for c in self.cards:
			s2c.setdefault(c.suit, []).append(c)
		for r in r2c: 
			r2c[r].sort()
			r2c[r].reverse()
		for s in s2c: 
			s2c[s].sort()
			s2c[s].reverse()
		self._find_straightflush(r2c,s2c) or \
		self._find_quads(r2c,s2c) or \
		self._find_fullhouse(r2c,s2c) or \
		self._find_flush(r2c,s2c) or \
		self._find_straight(r2c,s2c) or \
		self._find_set(r2c,s2c) or \
		self._find_twopair(r2c,s2c) or \
		self._find_pair(r2c,s2c) or \
		self._find_highcard(r2c,s2c)
		return r2c, s2c

	# for debugging/testing.
	def _analysis_to_str(self, r2c=None, s2c=None):
		if not r2c:
			r2c, s2c = self._analyze() 
		s = "r2c:\n"
		for rank in r2c:
			s += '> %s: %s' % (RANK_ABBR[rank], ' '.join([str(c) for c in r2c[rank]]))
			s += '\n'
		s += "s2c:\n"
		for suit in s2c:
			s += '> %s: %s' % (SUIT_ABBR[suit], ' '.join([str(c) for c in s2c[suit]]))
			s += '\n'
		s += 'type:%s\n' % TYPE_NAMES[self.type]
		s += 'ranks:%s\n' % ' '.join([RANK_ABBR[r] for r in self.ranks])
		return s

	# return the largest rank such that n cards have the rank.
	def _largest_rank_with_n(self, r2c, n, ignore0 = -1, ignore1 = -1):
		for r in range(ACE, TWO-1, -1):
			if r != ignore0 and r != ignore1 and len(r2c.get(r, [])) == n: 
				return r
		return -1

	# find n 'kicker' cards that do not have rank ignore1 nor ignore2.
	def _kickers(self, n, ignore0 = -1, ignore1 = -1):
		ranks = [c.rank for c in self.cards if c.rank != ignore0 and c.rank != ignore1]
		ranks.sort()
		ranks.reverse()
		return ranks[0:n]

	def _find_straightflush(self, r2c, s2c):
		if not self._find_straight(r2c,s2c):
			return False
		tally = [0,0,0,0]
		for s in range(4):
			for r in self.ranks:
				if len([c for c in r2c[r] if c.suit == s]) > 0:
					tally[s] += 1
			if tally[s] >= 5:
				self.type = STRAIGHTFLUSH
				if self.ranks[0] == ACE:
                                        self.type = SUPERSTRAIGHTFLUSH
					self.desc = 'royal flush'
				else:
					self.desc = '%s-high straight flush' % RANK_NAME[self.ranks[0]]
				return True
		return False

	def _find_quads(self, r2c, s2c):
		r = self._largest_rank_with_n(r2c, 4)
		if r == -1:
			return False
		self.type = QUADS
		self.ranks = [r,r,r,r] + self._kickers(1, r)
		self.desc = 'four of a kind (%s)' % _pluralize_rank(RANK_NAME[r])
		return True

	def _find_fullhouse(self, r2c, s2c):
		trip_rank = self._largest_rank_with_n(r2c, 3)
		if trip_rank == -1:
			return False
		pair_rank = self._largest_rank_with_n(r2c, 2, trip_rank)
		if pair_rank == -1:
			return False
		self.type = FULLHOUSE
		self.ranks = [trip_rank, trip_rank, trip_rank, pair_rank, pair_rank]
		self.desc = 'full house (%s over %s)' % (_pluralize_rank(RANK_NAME[max(trip_rank, pair_rank)]), _pluralize_rank(RANK_NAME[min(trip_rank, pair_rank)]))
		return True

	def _find_flush(self, r2c, s2c):
		for s in range(4):
			if len(s2c.get(s,[])) >= 5:
				self.type = FLUSH
				self.ranks = [c.rank for c in s2c[s][0:5]]
				self.desc = '%s-high flush' % RANK_NAME[self.ranks[0]]
				return True
		return False

	def _find_straight(self, r2c, s2c):
		r, n = ACE, 0
		while r >= TWO:
			if len(r2c.get(r, [])) > 0:
				n = n + 1
				if n == 5: break
			else:
				n = 0
			r = r - 1
		found = False
		if n == 5:
			found = True
			self.ranks = range(r + n - 1, r - 1, -1)
		elif n == 4 and r < TWO and len(r2c.get(ACE, [])) > 0:
			self.ranks = [FIVE, FOUR, THREE, TWO, ACE]
			found = True
		if found:
			self.type = STRAIGHT
			self.desc = '%s-high straight' % RANK_NAME[self.ranks[0]]
		return found

	def _find_set(self, r2c, s2c):
		r = self._largest_rank_with_n(r2c, 3)
		if r == -1:
			return False
		self.type = SET
		self.ranks = [r,r,r] + self._kickers(2, r)
		self.desc = 'three of a kind (%s)' % _pluralize_rank(RANK_NAME[r])
		return True

	def _find_twopair(self, r2c, s2c):
		r0 = self._largest_rank_with_n(r2c, 2)
		if r0 == -1:
			return False
		r1 = self._largest_rank_with_n(r2c, 2, r0)
		if r1 == -1:
			return False
		self.type = TWOPAIR
		min_r, max_r = (min(r0,r1), max(r0,r1))
		self.ranks = [max_r, max_r, min_r, min_r] + self._kickers(1, r0, r1)
		self.desc = 'two pair (%s and %s)' % (_pluralize_rank(RANK_NAME[max_r]), _pluralize_rank(RANK_NAME[min_r]))
		return True

	def _find_pair(self, r2c, s2c):
		r = self._largest_rank_with_n(r2c, 2)
		if r == -1:
			return False
		self.type = PAIR
		self.ranks = [r,r] + self._kickers(3, r)
		self.desc = 'pair of %s' % _pluralize_rank(RANK_NAME[r])
		return True

	def _find_highcard(self, r2c, s2c):
		self.type = HIGHCARD
		self.ranks = self._kickers(5)
		self.desc = '%s-high' % RANK_NAME[self.ranks[0]]
		return True

class Card(object):

	def __init__(self, val):
		self.suit = val / 13
		self.rank = val % 13

	def __cmp__(self, other):
		return cmp(self.rank, other.rank)
		
	def __str__(self):
		return self.describe(long_fmt=False)

	def describe(self, long_fmt=False):       
		if long_fmt:
			return '%s of %s' % (RANK_NAME[self.rank], SUIT_NAME[self.suit])
		return RANK_ABBR[self.rank] + SUIT_ABBR[self.suit]

def makeRequest(url,data):
    import urllib,urllib2,json
    params = urllib.urlencode(data)
    response = urllib2.urlopen(url, params)
    data = response.read()
    response.close()
    try:
        result = json.read(data)
        if result['server_now'] == 0 and result['return_code'] == 100 :
            result = None
        return result
    except :
        return None

