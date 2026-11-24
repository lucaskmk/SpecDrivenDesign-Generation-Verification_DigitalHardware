import cocotb
import json

@cocotb.test()
async def inventory_visible_hierarchy(dut):
    paths = []
    def visit(handle, path, depth):
        if depth > 2 or len(paths) >= 64:
            return
        try:
            children = list(handle)
        except Exception:
            children = []
        for child in children:
            name = getattr(child, "_name", None) or getattr(child, "name", None)
            if not name:
                continue
            child_path = path + "." + str(name)
            paths.append(child_path)
            visit(child, child_path, depth + 1)
    visit(dut, "dut", 0)
    cocotb.log.info("RVGEN_HIERARCHY=" + json.dumps(paths))
    assert True
