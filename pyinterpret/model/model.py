"""Model class."""

import abc
import numpy as np
from sklearn.preprocessing import LabelEncoder, OneHotEncoder

from ..util.static_types import StaticTypes, return_data_type
from ..util.logger import build_logger
from ..util import exceptions

class Model(object):
    """What is a model? A model needs to make predictions, so a means of
    passing data into the model, and receiving results.

    Goals:
        We want to abstract away how we access the model.
        We want to make inferences about the format of the output.
        We want to able to map model outputs to some smaller, universal set of output types.
        We want to infer whether the model is real valued, or classification (n classes?)
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, log_level=30):
        """
        Base model class for wrapping prediction functions. Common methods
        involve output type inference in requiring predict methods

        Parameters
        ----------
            log_level: int
                0, 10, 20, 30, 40, or 50 for verbosity of logs.


        Attributes
        ----------
            model_type: string

        """
        self._log_level = log_level
        self.logger = build_logger(log_level, __name__)
        self.examples = np.array(None)
        self.model_type = StaticTypes.unknown
        self.output_var_type = StaticTypes.unknown
        self.output_shape = StaticTypes.unknown
        self.n_classes = StaticTypes.unknown
        self.input_shape = StaticTypes.unknown
        self.probability = StaticTypes.unknown
        self.formatter = lambda x: x

    @abc.abstractmethod
    def predict(self, *args, **kwargs):
        """
        The way in which the submodule predicts values given an input
        """
        return

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def set_examples(self, examples):
        """
        Ties examples to self. equivalent to self.examples = np.array(examples).
        Parameters
        ----------
        examples: array type


        """
        self.examples = np.array(examples)

    def check_output_signature(self, examples):
        """
        Determines the model_type, output_type. Side effects
        of this method are to mutate object's attributes (model_type,
        n_classes, etc).

        Parameters
        ----------
        examples: pandas.DataFrame or numpy.ndarray
            The examples that will be passed through the predict function.
            The outputs from these examples will be used to make inferences
            about the types of outputs the function generally makes.

        """
        if not examples.any():
            err_msg = "Examples have not been provided. Cannot check outputs"
            raise exceptions.ModelError(err_msg)

        outputs = self(examples)
        self.input_shape = examples.shape
        self.output_shape = outputs.shape
        if len(self.output_shape) == 1:
            # the predict function is either a continuous prediction,
            # or a most-likely classification
            example_output = outputs[0]
            self.output_var_type = return_data_type(example_output)
            if self.output_var_type in (StaticTypes.output_types.string,
                                        StaticTypes.output_types.int):
                # the prediction is yield groups as strings or ints,
                # as in a classification model
                self.model_type = StaticTypes.model_types.classifier
                self.probability = False
                self.n_classes = len(np.unique(outputs))

            elif self.output_var_type == StaticTypes.output_types.float:
                # the prediction returning 1D continuous values
                # this is not a stable method
                # technically, you could classify things as
                # something like 0.0 and 1.0
                # perhaps it would be better if counted unique values?
                self.model_type = StaticTypes.model_types.regressor
                self.n_classes = 1
                self.probability = StaticTypes.not_applicable
                self.logger.warn("Inferring model type to be a regressor"
                                 "due to 1D array of floats")
            else:
                pass  # default unknowns will take care of this
        elif len(self.output_shape) == 2:
            self.model_type = StaticTypes.model_types.classifier
            self.n_classes = self.output_shape[1]
            example_output = outputs[0][0]
            self.output_var_type = return_data_type(example_output)
            self.probability = (self.output_var_type == StaticTypes.output_types.float)
        else:
            raise ValueError("Unsupported model type, output dim = 3")

        self.formatter = self.return_transformer_func()

        reports = self.model_report(examples)
        for report in reports:
            self.logger.debug(report)

    @staticmethod
    def predict_function_transformer(output):
        """
        Call this method when model returns a 1D array of
        predicted classes. The output is one hot encoded version.

        Parameters
        ----------
        output: array type
            The output of the pre-formatted predict function

        Returns
        ----------
        output: numpy.ndarray
            The one hot encoded outputs of predict_fn
        """

        label_encoder = LabelEncoder()
        _labels = label_encoder.fit_transform(output)[:, np.newaxis]
        # class_names = label_encoder.classes_.tolist()

        onehot_encoder = OneHotEncoder()
        output = onehot_encoder.fit_transform(_labels).todense()
        output = np.squeeze(np.asarray(output))
        return output

    def return_transformer_func(self):
        """
        In the event that the predict func returns 1D array of predictions,
        then this returns a formatter to convert outputs to a 2D one hot encoded
        array.

        For instance, if:
            predict_fn(data) -> ['apple','banana']
        then
            transformer = Model.return_transformer_func()
            transformer(predict_fn(data)) -> [[1, 0], [0, 1]]

        Returns
        ----------
        (callable):
            formatter function to wrap around predict_fn
        """

        # Note this expression below assumptions (not probability) evaluates to false if
        # and only if the model does not return probabilities. If unknown, should be true
        if self.model_type == StaticTypes.model_types.classifier and not self.probability:
            return self.predict_function_transformer
        else:
            return lambda x: x

    def model_report(self, examples):
        """
        Just returns a list of model attributes as a list

        Parameters
        ----------
        examples: array type:
            Examples to use for which we report behavior of predict_fn.


        Returns
        ----------
        reports: list of strings
            metadata about function.

        """
        reports = []
        if isinstance(self.examples, np.ndarray):
            raw_predictions = self.predict(examples)
            reports.append("Example: {} \n".format(examples[0]))
            reports.append("Outputs: {} \n".format(raw_predictions[0]))
        reports.append("Model type: {} \n".format(self.model_type))
        reports.append("Output Var Type: {} \n".format(self.output_var_type))
        reports.append("Output Shape: {} \n".format(self.output_shape))
        reports.append("N Classes: {} \n".format(self.n_classes))
        reports.append("Input Shape: {} \n".format(self.input_shape))
        reports.append("Probability: {} \n".format(self.probability))
        return reports