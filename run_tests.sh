#!/bin/bash
# Marstek Cloud - Test Runner Script
# Usage: ./run_tests.sh [OPTIONS]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Marstek Cloud Test Runner ===${NC}\n"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}\n"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -q -r requirements_test.txt
echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# Parse command line arguments
case "${1:-default}" in
    "quick")
        echo -e "${GREEN}Running quick tests (no coverage)...${NC}\n"
        pytest -v
        ;;
    "coverage")
        echo -e "${GREEN}Running tests with coverage report...${NC}\n"
        pytest --cov=custom_components.marstek_cloud --cov-report=term-missing --cov-report=html
        echo -e "\n${GREEN}✓ HTML coverage report generated in htmlcov/index.html${NC}"
        ;;
    "coordinator")
        echo -e "${GREEN}Running coordinator tests only...${NC}\n"
        pytest tests/test_coordinator.py -v
        ;;
    "config")
        echo -e "${GREEN}Running config flow tests only...${NC}\n"
        pytest tests/test_config_flow.py -v
        ;;
    "sensor")
        echo -e "${GREEN}Running sensor tests only...${NC}\n"
        pytest tests/test_sensor.py -v
        ;;
    "init")
        echo -e "${GREEN}Running init tests only...${NC}\n"
        pytest tests/test_init.py -v
        ;;
    "verbose")
        echo -e "${GREEN}Running tests with verbose output and logging...${NC}\n"
        pytest -vv -s --log-cli-level=DEBUG
        ;;
    "help")
        echo "Usage: ./run_tests.sh [OPTION]"
        echo ""
        echo "Options:"
        echo "  default      Run all tests with standard output (default)"
        echo "  quick        Run all tests without coverage"
        echo "  coverage     Run tests with full coverage report"
        echo "  coordinator  Run only coordinator tests"
        echo "  config       Run only config flow tests"
        echo "  sensor       Run only sensor tests"
        echo "  init         Run only init tests"
        echo "  verbose      Run tests with verbose output and debug logging"
        echo "  help         Show this help message"
        exit 0
        ;;
    *)
        echo -e "${GREEN}Running all tests...${NC}\n"
        pytest -v
        ;;
esac

# Show summary
echo -e "\n${GREEN}=== Test run complete! ===${NC}"
