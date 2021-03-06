import warnings
import sys

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.model_selection import KFold

from asl_utils import combine_sequences


class ModelSelector(object):
    '''
    base class for model selection (strategy design pattern)
    '''

    def __init__(self, all_word_sequences: dict, all_word_Xlengths: dict, this_word: str,
                 n_constant=3,
                 min_n_components=2, max_n_components=10,
                 random_state=14, verbose=False):
        self.words = all_word_sequences
        self.hwords = all_word_Xlengths
        self.sequences = all_word_sequences[this_word]
        self.X, self.lengths = all_word_Xlengths[this_word]
        self.this_word = this_word
        self.n_constant = n_constant
        self.min_n_components = min_n_components
        self.max_n_components = max_n_components
        self.random_state = random_state
        self.verbose = verbose

    def select(self):
        raise NotImplementedError

    def base_model(self, num_states):
        # with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        # warnings.filterwarnings("ignore", category=RuntimeWarning)

        try:
            hmm_model = GaussianHMM(n_components=num_states, covariance_type="diag", n_iter=1000,
                                    random_state=self.random_state, verbose=False).fit(self.X, self.lengths)
            if self.verbose:
                print("model created for {} with {} states".format(self.this_word, num_states))
            return hmm_model
        except:
            if self.verbose:
                print("failure on {} with {} states".format(self.this_word, num_states))
            return None


class SelectorConstant(ModelSelector):
    """ select the model with value self.n_constant

    """

    def select(self):
        """ select based on n_constant value

        :return: GaussianHMM object
        """
        best_num_components = self.n_constant
        return self.base_model(best_num_components)


class SelectorBIC(ModelSelector):
    """ select the model with the lowest Bayesian Information Criterion(BIC) score

    http://www2.imm.dtu.dk/courses/02433/doc/ch6_slides.pdf
    Bayesian information criteria: BIC = -2 * logL + p * logN
    """

    def select(self):
        """ select the best model for self.this_word based on
        BIC score for n between self.min_n_components and self.max_n_components

        :return: GaussianHMM object
        """
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score = float("inf")
        best_model_so_far = None

        for num_states in range(self.min_n_components, self.max_n_components + 1):
            try:
                model = self.base_model(num_states)
                p = num_states * (num_states - 1) + 2 * len(self.X[0]) * num_states
                score = -2 * model.score(self.X, self.lengths) + p * np.log(len(self.X))

                if score < best_score:
                    best_score = score
                    best_model_so_far = model
            except:
                print("Unexpected error:", sys.exc_info()[0])
                continue

        if not best_model_so_far:
            return self.base_model(self.n_constant)

        return best_model_so_far


class SelectorDIC(ModelSelector):
    """ select best model based on Discriminative Information Criterion

    Biem, Alain. "A model selection criterion for classification: Application to hmm topology optimization."
    Document Analysis and Recognition, 2003. Proceedings. Seventh International Conference on. IEEE, 2003.
    http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.58.6208&rep=rep1&type=pdf
    https://pdfs.semanticscholar.org/ed3d/7c4a5f607201f3848d4c02dd9ba17c791fc2.pdf
    DIC = log(P(X(i)) - 1/(M-1)SUM(log(P(X(all but i))
    """

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score_so_far = float("-inf")
        best_number_of_components = 0

        for num_states in range(self.min_n_components, self.max_n_components + 1):
            try:
                log_likelihood_of_i = self.base_model(num_states).score(self.X, self.lengths)

                words = list(self.words.keys())
                number_of_words = len(words)
                words.remove(self.this_word)

                accumulated_log_likelihood_of_all_words_except_i = 0
                for word in words:
                    try:
                        model_selector_all_words_except_i = ModelSelector(self.words,
                                                                          self.hwords,
                                                                          word,
                                                                          self.n_constant,
                                                                          self.min_n_components,
                                                                          self.max_n_components,
                                                                          self.random_state,
                                                                          self.verbose)
                        model_selector_X = model_selector_all_words_except_i.X
                        model_selector_lengths = model_selector_all_words_except_i.lengths
                        model_selector_score = model_selector_all_words_except_i.base_model(num_states) \
                            .score(model_selector_X, model_selector_lengths)
                        accumulated_log_likelihood_of_all_words_except_i += model_selector_score
                    except:
                        number_of_words -= 1

                    score = log_likelihood_of_i - accumulated_log_likelihood_of_all_words_except_i / (
                            number_of_words - 1)

                    if score > best_score_so_far:
                        best_score_so_far = score
                        best_number_of_components = num_states
            except:
                print("Unexpected error:", sys.exc_info()[0])
                continue

        if not best_number_of_components:
            return self.base_model(self.n_constant)

        return self.base_model(best_number_of_components)


class SelectorCV(ModelSelector):
    """ select best model based on average log Likelihood of cross-validation folds

    """

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score_so_far = float("-inf")
        best_model_so_far = None

        for num_states in range(self.min_n_components, self.max_n_components + 1):
            sum_log_likelihood = 0
            count_log_likelihood = 0

            try:
                split_method = KFold()
                for cv_train_idx, _ in split_method.split(self.sequences):
                    X, lengths = combine_sequences(cv_train_idx, self.sequences)
                    model = self.base_model(num_states)

                    try:
                        sum_log_likelihood = model.score(X, lengths)
                        count_log_likelihood += 1
                    except:
                        pass

                score = sum_log_likelihood / count_log_likelihood

                if score > best_score_so_far:
                    best_score_so_far = score
                    best_model_so_far = model
            except:
                print("Unexpected error:", sys.exc_info()[0])
                continue

        if not best_model_so_far:
            return self.base_model(self.n_constant)

        return best_model_so_far
