test3:
	python -m berghain.cli --scenario 3 --test-run logs/scenario3/995d056e-1490-492a-ba4e-a90c56757671.txt | tail -50

test2:
	python -m berghain.cli --scenario 2 --test-run logs/scenario2/aea2f08e-445f-44f4-a7c1-caff612d12dc.txt | tail -50

test1:
	python -m berghain.cli --scenario 1 --test-run logs/scenario1/4e8b6456-0258-41d1-b735-026a7c553f57.txt | tail -50
