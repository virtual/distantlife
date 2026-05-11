#!/usr/bin/env bash
# Test runner script with isolated database
# This script ensures tests don't modify the development database by:
# 1. Creating a temporary copy of the database
# 2. Running all tests against the copy
# 3. Automatically cleaning up the copy when done (even if tests fail)

set -e  # Exit immediately if any command fails

# Generate a unique temp database filename using the process ID ($$)
# This allows multiple test runs to run in parallel without conflicts
TEST_DB=".local/distantlife_test_$$.db"

# Define cleanup function to remove the temporary test database
cleanup() {
	rm -f "$TEST_DB"
}

# Register cleanup function to run on script exit (successful or failed)
# This ensures the temp database is deleted even if tests fail
trap cleanup EXIT

# Copy the development database to the temporary location
# This gives tests a fresh copy to work with
cp "distantlife.db" "$TEST_DB"

# Export SQLITE_DB_PATH environment variable pointing to the temp copy
# The connections.py file reads this variable to override the default DB path
export SQLITE_DB_PATH="$TEST_DB"

# Discover and run all test files matching test_*.py in the tests/ directory
# The -v flag enables verbose output showing test names and results
python -m unittest discover -s tests -p "test_*.py" -v
