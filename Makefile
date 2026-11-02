SIM ?= verilator
TOPLEVEL ?= rv32i_cpu
COCOTB_TEST_MODULES ?= test_rv32i
SV_DIR := $(CURDIR)/sv
MOCK_DIR := $(SV_DIR)/mock_cpu
PY_DIR := $(CURDIR)/cocotb
# Design under test: the mock CPU by default. For your own multi-file CPU set
# SV_FILELIST (a Verilator file list) or an ordered VERILOG_SOURCES list.
SV_FILELIST ?=
SV_INCDIRS ?=
ifneq ($(strip $(SV_FILELIST)),)
VERILOG_SOURCES :=
override COMPILE_ARGS += -F $(abspath $(SV_FILELIST))
else ifeq ($(origin VERILOG_SOURCES),undefined)
VERILOG_SOURCES := $(MOCK_DIR)/rv32i_pkg.sv $(MOCK_DIR)/mock_rv32i_cpu.sv
override COMPILE_ARGS += -I$(MOCK_DIR)
endif
override COMPILE_ARGS += $(addprefix -I,$(SV_INCDIRS))
export COMPILE_ARGS
export PYTHONPATH := $(PY_DIR):$(PYTHONPATH)
RESULTS_DIR ?= $(CURDIR)/results
SIM_BUILD ?= $(RESULTS_DIR)/sim_build
export COCOTB_RESULTS_FILE ?= $(RESULTS_DIR)/results.xml
export COCOTB_COVERAGE_FILE ?= $(RESULTS_DIR)/coverage.json
INSTRUCTIONS ?= all
export RV32I_INSTRUCTIONS := $(INSTRUCTIONS)

# Pruebas a nivel de programa (cocotb/test_programs.py).
#   make test_programs                     -> todos los programas
#   make test_programs PROGRAMS=factorial  -> solo uno (regex sobre el nombre)
PROGRAMS ?=
PROGRAMS_RESULTS_FILE ?= $(RESULTS_DIR)/results_programs.xml
ifneq ($(strip $(PROGRAMS)),)
export COCOTB_TEST_FILTER := $(PROGRAMS)
endif

.PHONY: test_cpu test_programs clean

test_cpu:
	@mkdir -p "$(RESULTS_DIR)"; \
	rm -f "$(COCOTB_RESULTS_FILE)" "$(COCOTB_COVERAGE_FILE)"; \
	rm -rf "$(SIM_BUILD)"; \
	set +e; \
	$(MAKE) -f "$$(cocotb-config --makefiles)/Makefile.sim" \
		SIM=$(SIM) SIM_BUILD="$(SIM_BUILD)" TOPLEVEL_LANG=verilog TOPLEVEL=$(TOPLEVEL) \
		COCOTB_TEST_MODULES=$(COCOTB_TEST_MODULES) \
		VERILOG_SOURCES="$(VERILOG_SOURCES)" COCOTB_RESULTS_FILE="$(COCOTB_RESULTS_FILE)"; \
	sim_status=$$?; \
	pytest -c "$(PY_DIR)/pytest.ini" --rootdir="$(PY_DIR)" --html="$(RESULTS_DIR)/dashboard_cpu.html" --self-contained-html "$(PY_DIR)/test_dashboard.py"; \
	report_status=$$?; \
	test $$sim_status -eq 0 -a $$report_status -eq 0

test_programs:
	@mkdir -p "$(RESULTS_DIR)"; \
	rm -f "$(PROGRAMS_RESULTS_FILE)"; \
	rm -rf "$(SIM_BUILD)"; \
	$(MAKE) -f "$$(cocotb-config --makefiles)/Makefile.sim" \
		SIM=$(SIM) SIM_BUILD="$(SIM_BUILD)" TOPLEVEL_LANG=verilog TOPLEVEL=$(TOPLEVEL) \
		COCOTB_TEST_MODULES=test_programs \
		VERILOG_SOURCES="$(VERILOG_SOURCES)" COCOTB_RESULTS_FILE="$(PROGRAMS_RESULTS_FILE)"

clean:
	$(MAKE) -f "$$(cocotb-config --makefiles)/Makefile.sim" SIM=$(SIM) SIM_BUILD="$(SIM_BUILD)" clean
	rm -f "$(COCOTB_RESULTS_FILE)" "$(RESULTS_DIR)/dashboard_cpu.html" "$(COCOTB_COVERAGE_FILE)" "$(PROGRAMS_RESULTS_FILE)"
	rm -rf $(PY_DIR)/__pycache__ $(PY_DIR)/.pytest_cache __pycache__ .pytest_cache