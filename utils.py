

def count_card(plate, card):
	return len([c for c in plate if c == card])


def remove_first_instance(list_to_remove, item):
	# in-place
	for n, i in enumerate(list_to_remove):
		if i == item:
			list_to_remove.pop(n)
			return

	raise ValueError("item %s not found in list %s" % (str(item), str(list_to_remove)))


def _test():
	l = [1, 2, 3, 1]
	remove_first_instance(l, 1)
	assert l == [2, 3, 1]

	l = [1, 2, 3, 1]
	remove_first_instance(l, 2)
	assert l == [1, 3, 1]

_test()
