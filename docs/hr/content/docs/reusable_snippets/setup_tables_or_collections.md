---
sidebar_label: Setup tables or collections
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<!-- TABS -->
# Setup tables or collections


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        # Note this is an optional step for MongoDB
        # Users can also work directly with `DataType` if they want to add
        # custom data
        from pinnacledb import Schema, DataType
        from pinnacledb.backends.mongodb import Collection
        
        table_or_collection = Collection('documents')
        USE_SCHEMA = False
        
        if USE_SCHEMA and isinstance(datatype, DataType):
            schema = Schema(fields={'x': datatype})
            db.apply(schema)        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb.backends.ibis import Table
        from pinnacledb.backends.ibis.field_types import FieldType
        
        if isinstance(datatype, DataType):
            schema = Schema(fields={'x': datatype})
        else:
            schema = Schema(fields={'x': FieldType(datatype)})
        
        table_or_collection = Table('documents', schema=schema)
        
        db.apply(table_or_collection)        
        ```
    </TabItem>
</Tabs>
