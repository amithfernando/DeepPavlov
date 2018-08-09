# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from deeppavlov.core.commands.utils import expand_path
from keras.preprocessing.sequence import pad_sequences
from deeppavlov.core.common.log import get_logger
import random

from deeppavlov.core.common.registry import register
from deeppavlov.core.models.estimator import Estimator
from typing import List, Callable

log = get_logger(__name__)


@register('ranking_vocab')
class RankingVocab(Estimator):
    # def __init__(self):
    #     pass
    #
    # def __call__(self):
    #     pass
    #
    # def fit(self):
    #     pass
    #
    # def load(self):
    #     pass
    #
    # def save(self):
    #     pass


    def __init__(self,
                 save_path: str,
                 load_path: str,
                 max_sequence_length: int,
                 max_token_length: int = None,
                 padding: str = 'post',
                 truncating: str = 'post',
                 token_embeddings: bool = True,
                 char_embeddings: bool = False,
                 char_pad: str = 'post',
                 char_trunc: str = 'post',
                 tok_dynamic_batch: bool = False,
                 char_dynamic_batch: bool = False,
                 update_embeddings: bool = False,
                 num_negative_samples: int = 10,
                 tokenizer: Callable = None,
                 seed: int = None,
                 **kwargs):

        self.max_sequence_length = max_sequence_length
        self.token_embeddings = token_embeddings
        self.char_embeddings = char_embeddings
        self.max_token_length = max_token_length
        self.padding = padding
        self.truncating = truncating
        self.char_pad = char_pad
        self.char_trunc = char_trunc
        self.tok_dynamic_batch = tok_dynamic_batch
        self.char_dynamic_batch = char_dynamic_batch
        self.upd_embs = update_embeddings
        self.num_negative_samples = num_negative_samples
        self.tokenizer = tokenizer

        save_path = expand_path(save_path).resolve()
        load_path = expand_path(load_path).resolve()

        self.char_save_path = save_path / "char2int.dict"
        self.char_load_path = load_path / "char2int.dict"
        self.tok_save_path = save_path / "tok2int.dict"
        self.tok_load_path = load_path / "tok2int.dict"
        self.cont_save_path = save_path / "cont2toks.dict"
        self.cont_load_path = load_path / "cont2toks.dict"
        self.resp_save_path = save_path / "resp2toks.dict"
        self.resp_load_path = load_path / "resp2toks.dict"
        self.cemb_save_path = str(save_path / "context_embs.npy")
        self.cemb_load_path = str(load_path / "context_embs.npy")
        self.remb_save_path = str(save_path / "response_embs.npy")
        self.remb_load_path = str(load_path / "response_embs.npy")

        self.int2tok_vocab = {}
        self.tok2int_vocab = {}
        self.response2toks_vocab = {}
        self.response2emb_vocab = {}
        self.context2toks_vocab = {}
        self.context2emb_vocab = {}

        random.seed(seed)

        super().__init__(load_path=load_path, save_path=save_path, **kwargs)


    def fit(self, context, response, pos_pool, neg_pool):
        log.info("[initializing new `{}`]".format(self.__class__.__name__))
        if self.char_embeddings:
            self.build_int2char_vocab()
            self.build_char2int_vocab()
        c_tok = self.tokenizer(context)
        r_tok = self.tokenizer(response)
        pos_pool_tok = [self.tokenizer(el) for el in pos_pool]
        if neg_pool[0] is not None:
            neg_pool_tok = [self.tokenizer(el) for el in neg_pool]
        else:
            neg_pool_tok = neg_pool
        self.build_int2tok_vocab(c_tok, r_tok, pos_pool_tok, neg_pool_tok)
        self.build_tok2int_vocab()
        self.build_context2toks_vocab(c_tok)
        self.build_response2toks_vocab(r_tok, pos_pool_tok, neg_pool_tok)
        if self.upd_embs:
            self.build_context2emb_vocab()
            self.build_response2emb_vocab()

    def load(self):
        log.info("[initializing `{}` from saved]".format(self.__class__.__name__))
        if self.char_embeddings:
            self.load_int2char()
            self.build_char2int_vocab()
        self.load_int2tok()
        self.build_tok2int_vocab()
        self.load_context2toks()
        self.load_response2toks()
        if self.upd_embs:
            self.load_cont()
            self.load_resp()

    def save(self):
        log.info("[saving `{}`]".format(self.__class__.__name__))
        if self.char_embeddings:
            self.save_int2char()
        self.save_int2tok()
        self.save_context2toks()
        self.save_response2toks()
        if self.upd_embs:
            self.save_cont()
            self.save_resp()

    def build_int2char_vocab(self):
        pass

    def build_int2tok_vocab(self, c_tok, r_tok, pos_pool_tok, neg_pool_tok):
        c = set([x for el in c_tok for x in el])
        r = set([x for el in r_tok for x in el])
        ppool = [x for el in pos_pool_tok for x in el]
        ppool = set([x for el in ppool for x in el])
        r = r | ppool
        if neg_pool_tok[0] is not None:
            npool = [x for el in neg_pool_tok for x in el]
            npool = set([x for el in npool for x in el])
            r = r | npool
        tok = c | r
        self.int2tok_vocab = {el[0]+1:el[1] for el in enumerate(tok)}
        self.int2tok_vocab[0] = '<UNK>'

    def build_response2toks_vocab(self, r_tok, pos_pool_tok, neg_pool_tok):
        r = set([' '.join(el) for el in r_tok])
        ppool = [x for el in pos_pool_tok for x in el]
        ppool = set([' '.join(el) for el in ppool])
        r = r | ppool
        if neg_pool_tok[0] is not None:
            npool = [x for el in neg_pool_tok for x in el]
            npool = set([' '.join(el) for el in npool])
            r = r | npool
        self.response2toks_vocab = {el[0]: el[1].split() for el in enumerate(r)}

    def build_context2toks_vocab(self, contexts):
        c = [' '.join(el) for el in contexts]
        c = set(c)
        self.context2toks_vocab = {el[0]: el[1].split() for el in enumerate(c)}


    def build_char2int_vocab(self):
        self.char2int_vocab = {el[1]: el[0] for el in self.int2char_vocab.items()}

    def build_tok2int_vocab(self):
        self.tok2int_vocab = {el[1]: el[0] for el in self.int2tok_vocab.items()}

    def build_response2emb_vocab(self):
        for i in range(len(self.response2toks_vocab)):
            self.response2emb_vocab[i] = None

    def build_context2emb_vocab(self):
        for i in range(len(self.context2toks_vocab)):
            self.context2emb_vocab[i] = None

    def conts2toks(self, conts_li):
        toks_li = [self.context2toks_vocab[cont] for cont in conts_li]
        return toks_li

    def resps2toks(self, resps_li):
        toks_li = [self.response2toks_vocab[resp] for resp in resps_li]
        return toks_li

    def make_toks(self, items_li, type):
        if type == "context":
            toks_li = self.conts2toks(items_li)
        elif type == "response":
            toks_li = self.resps2toks(items_li)
        return toks_li

    def __call__(self, context, response, pos_pool, neg_pool):
        c_tok = self.tokenizer(context)
        r_tok = self.tokenizer(response)
        pos_pool_tok = [self.tokenizer(el) for el in pos_pool]
        if neg_pool[0] is not None:
            neg_pool_tok = [self.tokenizer(el) for el in neg_pool]
        else:
            neg_pool_tok = neg_pool
        c = [el for el in self.make_ints(c_tok)]
        r = [el for el in self.make_ints(r_tok)]
        ppool = [self.make_ints(el) for el in pos_pool]
        if neg_pool[0] is not None:
            npool =[self.make_ints(el) for el in neg_pool_tok]
        else:
            npool = [self.make_ints(self.generate_items(el)) for el in pos_pool_tok]

        return c, r, ppool, npool

    def generate_items(self, pos_pool):
        candidates = []
        for i in range(self.num_negative_samples):
            candidate = self.response2toks_vocab[random.randint(0, len(self.response2toks_vocab)-1)]
            while candidate in pos_pool:
                candidate = self.response2toks_vocab[random.randint(0, len(self.response2toks_vocab)-1)]
            candidates.append(candidate)
        return candidates

    def make_ints(self, toks_li):
        if self.tok_dynamic_batch:
            msl = min(max([len(el) for el in toks_li]), self.max_sequence_length)
        else:
            msl = self.max_sequence_length
        if self.char_dynamic_batch:
            mtl = min(max(len(x) for el in toks_li for x in el), self.max_token_length)
        else:
            mtl = self.max_token_length

        if self.token_embeddings and not self.char_embeddings:
            return self.make_tok_ints(toks_li, msl)
        elif not self.token_embeddings and self.char_embeddings:
            return self.make_char_ints(toks_li, msl, mtl)
        elif self.token_embeddings and self.char_embeddings:
            tok_ints = self.make_tok_ints(toks_li, msl)
            char_ints = self.make_char_ints(toks_li, msl, mtl)
            return np.concatenate([np.expand_dims(tok_ints, axis=2), char_ints], axis=2)

    def make_tok_ints(self, toks_li, msl):
        ints_li = []
        for toks in toks_li:
            ints = []
            for tok in toks:
                index = self.tok2int_vocab.get(tok)
                if self.tok2int_vocab.get(tok) is not None:
                    ints.append(index)
                else:
                    ints.append(0)
            ints_li.append(ints)
        ints_li = pad_sequences(ints_li,
                                maxlen=msl,
                                padding=self.padding,
                                truncating=self.truncating)
        return ints_li

    def make_char_ints(self, toks_li, msl, mtl):
        ints_li = np.zeros((len(toks_li), msl, mtl))

        for i, toks in enumerate(toks_li):
            if self.truncating == 'post':
                toks = toks[:msl]
            else:
                toks = toks[-msl:]
            for j, tok in enumerate(toks):
                if self.padding == 'post':
                    k = j
                else:
                    k = j + msl - len(toks)
                ints = []
                for char in tok:
                    index = self.char2int_vocab.get(char)
                    if index is not None:
                        ints.append(index)
                    else:
                        ints.append(0)
                if self.char_trunc == 'post':
                    ints = ints[:mtl]
                else:
                    ints = ints[-mtl:]
                if self.char_pad == 'post':
                    ints_li[i, k, :len(ints)] = ints
                else:
                    ints_li[i, k, -len(ints):] = ints
        return ints_li

    def save_int2char(self):
        with self.char_save_path.open('w') as f:
            f.write('\n'.join(['\t'.join([str(el[0]), el[1]]) for el in self.int2char_vocab.items()]))

    def load_int2char(self):
        with self.char_load_path.open('r') as f:
            data = f.readlines()
        self.int2char_vocab = {int(el.split('\t')[0]): el.split('\t')[1][:-1] for el in data}

    def save_int2tok(self):
        with self.tok_save_path.open('w') as f:
            f.write('\n'.join(['\t'.join([str(el[0]), el[1]]) for el in self.int2tok_vocab.items()]))

    def load_int2tok(self):
        with self.tok_load_path.open('r') as f:
            data = f.readlines()
        self.int2tok_vocab = {int(el.split('\t')[0]): el.split('\t')[1][:-1] for el in data}

    def save_context2toks(self):
        with self.cont_save_path.open('w') as f:
            f.write('\n'.join(['\t'.join([str(el[0]), ' '.join(el[1])]) for el in self.context2toks_vocab.items()]))

    def load_context2toks(self):
        with self.cont_load_path.open('r') as f:
            data = f.readlines()
        self.context2toks_vocab = {int(el.split('\t')[0]): el.split('\t')[1][:-1].split(' ') for el in data}

    def save_response2toks(self):
        with self.resp_save_path.open('w') as f:
            f.write(
                '\n'.join(['\t'.join([str(el[0]), ' '.join(el[1])]) for el in self.response2toks_vocab.items()]))

    def load_response2toks(self):
        with self.resp_load_path.open('r') as f:
            data = f.readlines()
        self.response2toks_vocab = {int(el.split('\t')[0]): el.split('\t')[1][:-1].split(' ') for el in data}

    def save_cont(self):
        context_embeddings = []
        for i in range(len(self.context2emb_vocab)):
            context_embeddings.append(self.context2emb_vocab[i])
        context_embeddings = np.vstack(context_embeddings)
        np.save(self.cemb_save_path, context_embeddings)

    def load_cont(self):
        context_embeddings_arr = np.load(self.cemb_load_path)
        for i in range(context_embeddings_arr.shape[0]):
            self.context2emb_vocab[i] = context_embeddings_arr[i]

    def save_resp(self):
        response_embeddings = []
        for i in range(len(self.response2emb_vocab)):
            response_embeddings.append(self.response2emb_vocab[i])
        response_embeddings = np.vstack(response_embeddings)
        np.save(self.remb_save_path, response_embeddings)

    def load_resp(self):
        response_embeddings_arr = np.load(self.remb_load_path)
        for i in range(response_embeddings_arr.shape[0]):
            self.response2emb_vocab[i] = response_embeddings_arr[i]
