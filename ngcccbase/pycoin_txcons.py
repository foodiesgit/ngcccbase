"""
pycoin_txcons.py

Construct and sign transactions using pycoin library
"""

from pycoin.tx.tx_utils import sign_tx as pycoin_sign_tx
from pycoin.encoding import bitcoin_address_to_hash160_sec,\
    wif_to_tuple_of_secret_exponent_compressed
from pycoin.serialize import b2h, b2h_rev

from pycoin.tx.Tx import Tx, SIGHASH_ALL
from pycoin.tx.TxIn import TxIn
from pycoin.tx.TxOut import TxOut

from pycoin.tx.script import tools
from pycoin.tx.script.vm import verify_script

from io import BytesIO
from pycoin.tx.pay_to import build_hash160_lookup


from coloredcoinlib import txspec
from coloredcoinlib.blockchain import script_to_raw_address


def construct_standard_tx(composed_tx_spec, is_test):
    txouts = []
    prefix = is_test and b'\x32' or b"\x32"
    STANDARD_SCRIPT_OUT = "OP_DUP OP_HASH160 %s OP_EQUALVERIFY OP_CHECKSIG"
    for txout in composed_tx_spec.get_txouts():
        hash160 = bitcoin_address_to_hash160_sec(txout.target_addr, 
                                                 address_prefix=prefix)
        script_text = STANDARD_SCRIPT_OUT % b2h(hash160)
        script_bin = tools.compile(script_text)
        txouts.append(TxOut(txout.value, script_bin))
    txins = []
    for cts_txin in composed_tx_spec.get_txins():
        txin = TxIn(cts_txin.get_txhash(), cts_txin.prevout.n)
        if cts_txin.nSequence:
            print cts_txin.nSequence
            txin.sequence = cts_txin.nSequence
        txins.append(txin)
    version = 1
    lock_time = 0
    return Tx(version, txins, txouts, lock_time)

def sign_tx(tx, utxo_list, is_test):
    secret_exponents = [utxo.address_rec.rawPrivKey
                        for utxo in utxo_list if utxo.address_rec]
    hash160_lookup = build_hash160_lookup(secret_exponents)
    txins = tx.txs_in[:]
    for txin_idx in xrange(len(txins)):
        blank_txin = txins[txin_idx]
        utxo = None
        for utxo_candidate in utxo_list:
            if utxo_candidate.get_txhash() == blank_txin.previous_hash \
                    and utxo_candidate.outindex == blank_txin.previous_index:
                utxo = utxo_candidate
                break
        if not (utxo and utxo.address_rec):
            continue
        txout_script = utxo.script.decode('hex')
        tx.sign_tx_in(hash160_lookup, txin_idx, txout_script, SIGHASH_ALL)

def deserialize(tx_data):
    return Tx.parse(BytesIO(tx_data))

def reconstruct_composed_tx_spec(model, tx):
    if isinstance(tx, str):
        tx = deserialize(tx)
    if not isinstance(tx, Tx):
        raise Exception('tx is neiether string nor pycoin.tx.Tx')

    pycoin_tx = tx

    composed_tx_spec = txspec.ComposedTxSpec(None)

    for py_txin in pycoin_tx.txs_in:
        # lookup the previous hash and generate the utxo
        in_txhash, in_outindex = py_txin.previous_hash, py_txin.previous_index
        in_txhash = in_txhash[::-1].encode('hex')

        composed_tx_spec.add_txin(
            txspec.ComposedTxSpec.TxIn(in_txhash, in_outindex))
        # in_tx = ccc.blockchain_state.get_tx(in_txhash)
        # value = in_tx.outputs[in_outindex].value
        # raw_address = script_to_raw_address(py_txin.script)
        # address = ccc.raw_to_address(raw_address)

    for py_txout in pycoin_tx.txs_out:
        script = py_txout.script
        raw_address = script_to_raw_address(script)
        if raw_address:
            address = model.ccc.raw_to_address(raw_address)
        else:
            address = None
        composed_tx_spec.add_txout(
            txspec.ComposedTxSpec.TxOut(py_txout.coin_value, address))

    return composed_tx_spec
