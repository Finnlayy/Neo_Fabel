"""Export a flatten→Gemm ONNX graph with input name lstm_input [1,10,4]."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def export_linear_onnx(
    weights: np.ndarray,
    bias: np.ndarray,
    path: Path,
    *,
    opset: int = 17,
) -> None:
    """
    weights: shape (40, 1) — maps flattened [1,40] → [1,1]
    bias: shape (1,)
    """
    from onnx import TensorProto, helper, numpy_helper, save
    from onnx.checker import check_model

    w = np.asarray(weights, dtype=np.float32).reshape(40, 1)
    b = np.asarray(bias, dtype=np.float32).reshape(1)

    x = helper.make_tensor_value_info("lstm_input", TensorProto.FLOAT, [1, 10, 4])
    y = helper.make_tensor_value_info("prediction", TensorProto.FLOAT, [1, 1])
    w_init = numpy_helper.from_array(w, name="W")
    b_init = numpy_helper.from_array(b, name="B")

    nodes = [
        helper.make_node("Flatten", ["lstm_input"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "W", "B"], ["prediction"], alpha=1.0, beta=1.0),
    ]
    graph = helper.make_graph(nodes, "neo_fabel_linear_lstm_proxy", [x], [y], [w_init, b_init])
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", opset)],
        producer_name="neo-fabel",
    )
    model.ir_version = 9
    check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    save(model, str(path))
