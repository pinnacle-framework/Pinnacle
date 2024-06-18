import glob
import os
import re
import sys
import typing as t

import ibis
import mongomock
import pandas
import pymongo
from prettytable import PrettyTable

import pinnacledb as s
from pinnacledb import logging
from pinnacledb.backends.base.backends import data_backends, metadata_stores
from pinnacledb.backends.base.data_backend import BaseDataBackend
from pinnacledb.backends.local.artifacts import FileSystemArtifactStore
from pinnacledb.backends.local.compute import LocalComputeBackend
from pinnacledb.backends.mongodb.artifacts import MongoArtifactStore
from pinnacledb.backends.mongodb.utils import get_avaliable_conn
from pinnacledb.backends.ray.compute import RayComputeBackend
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.misc.anonymize import anonymize_url


def _get_metadata_store(cfg):
    # try to connect to the metadata store specified in the configuration.
    logging.info("Connecting to Metadata Client:", cfg.metadata_store)
    return _build_databackend_impl(cfg.metadata_store, metadata_stores, type='metadata')


def _build_metadata(cfg, databackend: t.Optional['BaseDataBackend'] = None):
    # Connect to metadata store.
    # ------------------------------
    # 1. try to connect to the metadata store specified in the configuration.
    # 2. if that fails, try to connect to the data backend engine.
    # 3. if that fails, try to connect to the data backend uri.
    if cfg.metadata_store is not None:
        return _get_metadata_store(cfg)
    else:
        try:
            # try to connect to the data backend engine.
            assert isinstance(databackend, BaseDataBackend)
            logging.info(
                "Connecting to Metadata Client with engine: ", databackend.conn
            )
            return databackend.build_metadata()
        except Exception as e:
            logging.warn("Error building metadata from DataBackend:", str(e))
            metadata = None

    if metadata is None:
        try:
            # try to connect to the data backend uri.
            logging.info("Connecting to Metadata Client with URI: ", cfg.data_backend)
            return _build_databackend_impl(
                cfg.data_backend, metadata_stores, type='metadata'
            )
        except Exception as e:
            # Exit quickly if a connection fails.
            logging.error("Error initializing to Metadata Client:", str(e))
            sys.exit(1)


def _build_databackend(cfg, databackend=None):
    # Connect to data backend.
    # ------------------------------
    try:
        if not databackend:
            databackend = _build_databackend_impl(cfg.data_backend, data_backends)
        logging.info("Data Client is ready.", databackend.conn)
    except Exception as e:
        # Exit quickly if a connection fails.
        logging.error("Error initializing to DataBackend Client:", str(e))
        sys.exit(1)
    return databackend


def _build_artifact_store(
    artifact_store: t.Optional[str] = None,
    databackend: t.Optional['BaseDataBackend'] = None,
):
    if not artifact_store:
        assert isinstance(databackend, BaseDataBackend)
        return databackend.build_artifact_store()

    if artifact_store.startswith('mongodb://'):
        import pymongo

        conn: pymongo.MongoClient = pymongo.MongoClient(
            '/'.join(artifact_store.split('/')[:-1])
        )
        name = artifact_store.split('/')[-1]
        return MongoArtifactStore(conn, name)
    elif artifact_store.startswith('filesystem://'):
        directory = artifact_store.split('://')[1]
        return FileSystemArtifactStore(directory)
    else:
        raise ValueError(f'Unknown artifact store: {artifact_store}')


# Helper function to build a data backend based on the URI.
def _build_databackend_impl(uri, mapping, type: str = 'data_backend'):
    logging.debug(f"Parsing data connection URI:{uri}")

    # TODO: Should we move the following code to the DataBackend classes?
    if re.match('^mongodb:\/\/', uri) is not None:
        name = uri.split('/')[-1]
        conn = get_avaliable_conn(uri, serverSelectionTimeoutMS=5000)
        return mapping['mongodb'](conn, name)

    elif re.match('^mongodb\+srv:\/\/', uri):
        name = uri.split('/')[-1]
        conn = pymongo.MongoClient(
            '/'.join(uri.split('/')[:-1]),
            serverSelectionTimeoutMS=5000,
        )
        return mapping['mongodb'](conn, name)

    elif uri.startswith('mongomock://'):
        name = uri.split('/')[-1]
        conn = mongomock.MongoClient()
        return mapping['mongodb'](conn, name)

    elif uri.endswith('.csv'):
        if type == 'metadata':
            raise ValueError('Cannot build metadata from a CSV file.')

        uri = uri.split('://')[-1]

        csv_files = glob.glob(uri)
        dir_name = os.path.dirname(uri)
        tables = {}
        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            if os.path.getsize(csv_file) == 0:
                df = pandas.DataFrame()
            else:
                df = pandas.read_csv(csv_file)
            tables[filename.split('.')[0]] = df
        ibis_conn = ibis.pandas.connect(tables)
        return mapping['ibis'](ibis_conn, dir_name, in_memory=True)

    else:
        name = uri.split('//')[0]
        if type == 'data_backend':
            ibis_conn = ibis.connect(uri)
            return mapping['ibis'](ibis_conn, name)
        else:
            assert type == 'metadata'
            from sqlalchemy import create_engine

            sql_conn = create_engine(uri)
            return mapping['sqlalchemy'](sql_conn, name)


def build_compute(compute):
    """
    Helper function to build compute backend.

    :param compute: Compute uri.
    """
    logging.info("Connecting to compute client:", compute)

    if compute is None:
        return LocalComputeBackend()

    return RayComputeBackend(compute)


def build_datalayer(cfg=None, databackend=None, **kwargs) -> Datalayer:
    """
    Build a Datalayer object as per ``db = pinnacle(db)`` from configuration.

    :param cfg: Configuration to use. If None, use ``pinnacledb.CFG``.
    :param databackend: Databacked to use.
                        If None, use ``pinnacledb.CFG.data_backend``.
    :param kwargs: keyword arguments to be adopted by the `CFG`
    """
    # Configuration
    # ------------------------------
    # Use the provided configuration or fall back to the default configuration.
    cfg = (cfg or s.CFG)(**kwargs)

    databackend = _build_databackend(cfg, databackend)
    metadata = _build_metadata(cfg, databackend)
    assert metadata

    artifact_store = _build_artifact_store(cfg.artifact_store, databackend)
    compute = build_compute(cfg.cluster.compute.uri)

    datalayer = Datalayer(
        databackend=databackend,
        metadata=metadata,
        artifact_store=artifact_store,
        compute=compute,
    )
    # Keep the real configuration in the datalayer object.
    datalayer.cfg = cfg

    show_configuration(cfg)
    return datalayer


def show_configuration(cfg):
    """Show the configuration.

    Only show the important configuration values and anonymize the URLs.

    :param cfg: The configuration object.
    """
    table = PrettyTable()
    table.field_names = ["Configuration", "Value"]
    # Only show the important configuration values.
    key_values = [
        ('Data Backend', anonymize_url(cfg.data_backend)),
        ('Metadata Store', anonymize_url(cfg.metadata_store)),
        ('Artifact Store', anonymize_url(cfg.artifact_store)),
        ('Compute', cfg.cluster.compute.uri),
        ('CDC', cfg.cluster.cdc.uri),
        ('Vector Search', cfg.cluster.vector_search.uri),
    ]
    for key, value in key_values:
        if value:
            table.add_row([key, value])

    logging.info(f"Configuration: \n {table}")
