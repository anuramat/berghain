spam scenario="3":
    echo {{ scenario }}
    while true; do python -m berghain.cli --scenario {{ scenario }}; done

test3:
    python -m berghain.cli --scenario 3 --test-run logs/scenario3/4f98fdf1-6fa4-4f33-b238-1dd4d49c714a.txt

test2:
    python -m berghain.cli --scenario 2 --test-run logs/scenario2/5907fc79-29a3-43e0-b175-48ef084b0dd2.txt

test1:
    python -m berghain.cli --scenario 1 --test-run logs/scenario1/a0aca8ef-c1b9-4cd4-8f07-bb8556a06946.txt
