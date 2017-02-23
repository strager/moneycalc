def iter_merge_sort(iterables, key):
    iterators = list(map(iter, iterables))
    cur_values = list(map(lambda iterator: next(iterator, None), iterators))
    active_indexes = set(index for (index, value) in enumerate(cur_values) if value is not None)
    while active_indexes:
        index = min(active_indexes, key=lambda index: key(cur_values[index]))
        assert cur_values[index] is not None
        yield cur_values[index]
        new_value = next(iterators[index], None)
        cur_values[index] = new_value
        if new_value is None:
            active_indexes.remove(index)
