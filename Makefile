.PHONY: run eval test demo json help

help:
	@echo "make run   - reconcile every account, print the report"
	@echo "make eval  - run the eval suite (expected vs actual verdicts)"
	@echo "make test  - run unit tests"
	@echo "make demo  - eval + a couple of illustrative single-account checks"
	@echo "make json  - emit machine-readable JSON for all accounts"

run:
	python3 -m src.run

eval:
	python3 -m eval.run_eval

test:
	python3 -m unittest discover -s tests -v

json:
	python3 -m src.run --json

demo: eval
	@echo "\n--- Implausible spike, number withheld (Torch Digital, ACC-2007) ---"
	@python3 -m src.run --account ACC-2007
	@echo "\n--- Multi-business-unit account, must sum (Solaris, ACC-2004) ---"
	@python3 -m src.run --account ACC-2004
