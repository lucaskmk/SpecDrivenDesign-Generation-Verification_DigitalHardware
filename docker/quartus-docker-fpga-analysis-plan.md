# Quartus Docker FPGA Analysis --- Implementation Notes

## Goal

Create a Docker image containing **Quartus Prime Lite** that can compile
and analyze FPGA projects in a reproducible environment.

The initial target FPGA is:

-   **Family:** Altera Cyclone V
-   **Device:** `5CEBA4F23C7N`
-   **Device support package:** Cyclone V

The image should remain **modular**, so support for additional FPGA
families can be added later without redesigning the Dockerfile.

------------------------------------------------------------------------

## Licensing

Quartus Prime **Lite Edition** does not require a Quartus license file
or license server for normal compilation of supported devices such as
the Cyclone V.

Separately licensed IP cores may still require their own licenses.

This makes Quartus Lite suitable for Docker and CI use because the basic
synthesis/fitting workflow does not require injecting a license secret.

------------------------------------------------------------------------

## What the Container Should Eventually Do

Given a Quartus project containing Verilog/VHDL and a selected FPGA, the
container should run the normal implementation flow:

``` text
Verilog / VHDL
      |
      v
  Synthesis
      |
      +----------> RTL / netlist information
      |
      v
    Fitter
      |
      +----------> Resource utilization / fit
      |
      v
   TimeQuest
      |
      +----------> Timing / Fmax
      |
      v
Power Analyzer
      |
      +----------> Estimated power
      |
      v
Programming file (.sof, etc.)
```

The main outputs we want are described below.

------------------------------------------------------------------------

## 1. Determine Whether the Design Fits

Quartus's **Fitter** knows the exact resources available on the selected
FPGA.

For `5CEBA4F23C7N`, Quartus can therefore determine whether the compiled
design fits and report resource utilization such as:

-   Logic/ALM utilization
-   Registers
-   Embedded memory / RAM blocks
-   DSP blocks
-   PLLs
-   I/O pins
-   Other device-specific resources

The automated result should ideally contain both absolute usage and
percentage utilization.

Example:

``` text
Target: 5CEBA4F23C7N

FIT
--------------------------------
Status:             PASS
Logic utilization:  12,431 / 18,480
Registers:          ...
RAM blocks:         ...
DSP blocks:         ...
PLLs:               ...
Pins:               ...
```

A failed fit should also be detectable programmatically.

------------------------------------------------------------------------

## 2. Timing and Maximum Clock Frequency

Use **TimeQuest Timing Analyzer** to obtain timing information.

Important outputs include:

-   Setup slack
-   Hold slack
-   Critical paths
-   Clock timing
-   Timing closure status
-   Fmax / achievable clock-frequency information

### Timing Constraints

Meaningful timing analysis requires proper `.sdc` constraints.

For example:

``` tcl
create_clock -name clk -period 10.000 [get_ports {clk}]
```

This defines a 10 ns clock period, corresponding to:

``` text
100 MHz
```

Quartus can then determine whether the implementation meets that
requirement and report the available timing margin.

The automated report could look like:

``` text
TIMING
--------------------------------
Target clock:       100.00 MHz
Estimated Fmax:     127.43 MHz
Worst slack:        +2.15 ns
Timing closure:     PASS
```

Do not treat an Fmax number as meaningful if the project has inadequate
timing constraints.

------------------------------------------------------------------------

## 3. Power Estimation

Use the **Quartus Power Analyzer** to estimate FPGA power consumption.

Useful categories include:

-   Static power
-   Dynamic power
-   I/O power
-   Total estimated power

Example:

``` text
POWER
--------------------------------
Static:             X.XXX W
Dynamic:            X.XXX W
I/O:                X.XXX W
Estimated total:    X.XXX W
```

### Important Limitation

Power is an **estimate**, not a guaranteed measurement.

Its accuracy depends on information such as:

-   Clock frequencies
-   Signal switching activity
-   I/O standards
-   Supply voltage
-   Temperature
-   Device configuration
-   Actual workload

For early feasibility analysis, Quartus's estimates are still useful.
For accurate hardware power characterization, measurements on the
physical board are ultimately required.

------------------------------------------------------------------------

## 4. RTL / Netlist Visualization

Quartus provides an **RTL Viewer** and other netlist viewers that can
show the synthesized design graphically.

This can expose:

-   Top-level hierarchy
-   Registers
-   Multiplexers
-   Combinational logic
-   Module connections
-   Synthesized structures

However, the RTL Viewer is primarily an interactive GUI tool.

A Docker-based automated workflow should investigate whether the desired
graph can be exported directly. If automatic PNG/SVG/PDF RTL diagrams
are required and Quartus cannot conveniently produce them headlessly, an
additional netlist-visualization tool may need to be included in the
image.

The Quartus-generated synthesis/netlist data should still be retained.

------------------------------------------------------------------------

## Modular FPGA Device Support

The Docker image should avoid installing every FPGA family by default.

Cyclone V support should be the initial/default device package because
the current target is:

``` text
5CEBA4F23C7N
```

Additional families should be installable through Docker build
arguments.

Conceptually:

``` bash
docker build \
    --build-arg DEVICE_SUPPORT="cyclonev cyclone10lp max10" \
    -t quartus-lite:25.1-multi .
```

The Dockerfile can map names such as:

``` text
cyclonev
cycloneiv
cyclone10lp
max10
max
```

to their corresponding Quartus device-support packages.

This keeps the base image smaller and makes FPGA support extensible.

------------------------------------------------------------------------

## Desired Automated Interface

Rather than exposing only the raw Quartus executables, eventually add a
wrapper command around the Quartus tools.

Desired usage:

``` bash
docker run --rm \
    -v "$PWD:/workspace" \
    quartus-analyzer \
    analyze \
    --project cpu.qpf
```

The wrapper should:

1.  Identify the Quartus project and selected device.
2.  Run synthesis.
3.  Run the fitter.
4.  Run timing analysis.
5.  Run power analysis.
6.  Collect useful reports.
7.  Detect failures.
8.  Convert important results into machine-readable output.
9.  Preserve the programming file when compilation succeeds.

------------------------------------------------------------------------

## Desired Output Structure

A useful standardized output directory would be:

``` text
quartus_output/
├── compilation/
│   └── ...
├── reports/
│   ├── resources.json
│   ├── timing.json
│   ├── power.json
│   └── summary.json
├── netlist/
│   └── ...
└── bitstream/
    └── cpu.sof
```

### `summary.json`

The most important information should be consolidated into one
machine-readable file.

Conceptually:

``` json
{
  "device": "5CEBA4F23C7N",
  "compilation": {
    "success": true
  },
  "fit": {
    "success": true,
    "logic_utilization_percent": 67.3
  },
  "timing": {
    "target_clock_mhz": 100.0,
    "fmax_mhz": 127.43,
    "worst_slack_ns": 2.15,
    "closure": true
  },
  "power": {
    "estimated_total_w": null
  }
}
```

The exact schema can be defined when implementing the wrapper.

------------------------------------------------------------------------

## Existing Basic Docker Usage

For the Cyclone V Quartus Lite image:

``` bash
docker build -t quartus-lite:25.1 .
```

A project can then be compiled by mounting it into the container:

``` bash
docker run --rm \
    -v "$PWD/project:/workspace" \
    quartus-lite:25.1 \
    --flow compile /workspace/my_project.qpf
```

------------------------------------------------------------------------

## Future Implementation Checklist

-   [ ] Build and test the Quartus Lite Docker image.
-   [ ] Confirm `5CEBA4F23C7N` is selectable and compiles correctly.
-   [ ] Verify Cyclone V device support is installed.
-   [ ] Test a minimal Verilog/VHDL project.
-   [ ] Extract Fitter resource utilization.
-   [ ] Detect whether the design fits.
-   [ ] Add `.sdc` timing constraints.
-   [ ] Extract TimeQuest timing results.
-   [ ] Extract Fmax information.
-   [ ] Extract critical-path/slack information.
-   [ ] Run Power Analyzer.
-   [ ] Extract static/dynamic/I/O/total power estimates.
-   [ ] Investigate headless RTL/netlist graph export.
-   [ ] Add a wrapper `analyze` command.
-   [ ] Convert reports to JSON.
-   [ ] Produce `summary.json`.
-   [ ] Preserve generated `.sof` files.
-   [ ] Add modular support for additional FPGA families.
-   [ ] Test the container in CI/headless environments.
-   [ ] Optionally add USB/JTAG passthrough instructions for physical
    FPGA programming.

------------------------------------------------------------------------

## Final Objective

The finished container should make it possible to provide:

``` text
FPGA project + target FPGA
            |
            v
       Docker image
            |
            v
         Quartus
            |
     +------+------+------+
     |      |      |      |
     v      v      v      v
    FIT   TIMING  POWER   RTL
     |      |      |      |
     +------+------+------+
            |
            v
       Machine-readable
       analysis reports
```

This turns Quartus from merely a tool installed inside Docker into a
reproducible **FPGA feasibility and implementation-analysis
environment** capable of answering:

-   Does this design compile?
-   Does it fit on this FPGA?
-   How much of the FPGA does it use?
-   What clock frequency can it achieve?
-   Does it meet the requested timing constraints?
-   Approximately how much power will it consume?
-   What does the synthesized RTL/netlist look like?
-   What programming file was generated?
