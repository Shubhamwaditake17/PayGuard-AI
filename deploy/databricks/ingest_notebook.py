# Databricks notebook source
# MAGIC %md
# MAGIC # PayGuard AI: knowledge-base ingestion on Databricks (Spark + Delta)
# MAGIC Upload `data/docs/*.md` to a Unity Catalog volume or DBFS, set `DOCS_PATH`, then run all cells.
# MAGIC Written from Databricks docs; run it on Databricks Community/Free Edition and adjust paths as needed.

# COMMAND ----------
import re
from pyspark.sql import functions as F, types as T

DOCS_PATH = "/Volumes/main/default/payguard/docs/*.md"   # change to your volume / dbfs:/ path

def chunk_text(text, max_words=90, overlap=20):
    heading, out = "", []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        if para.startswith("#"):
            heading = para.lstrip("# ").strip(); continue
        words, i = para.split(), 0
        while i < len(words):
            body = " ".join(words[i:i + max_words])
            out.append(f"{heading}: {body}" if heading else body)
            if i + max_words >= len(words): break
            i += max_words - overlap
    return out

chunk_udf = F.udf(chunk_text, T.ArrayType(T.StringType()))

# COMMAND ----------
raw = spark.read.format("text").option("wholetext", True).load(DOCS_PATH) \
          .withColumn("source", F.element_at(F.split(F.input_file_name(), "/"), -1))
chunks = (raw.withColumn("chunk", F.explode(chunk_udf("value")))
             .withColumn("chunk_id", F.concat_ws("#", F.col("source"), F.monotonically_increasing_id()))
             .select("chunk_id", "source", "chunk"))
chunks.write.format("delta").mode("overwrite").saveAsTable("payguard_chunks")
display(spark.table("payguard_chunks"))

# COMMAND ----------
# MAGIC %sql
# MAGIC SELECT source, COUNT(*) AS n_chunks FROM payguard_chunks GROUP BY source ORDER BY source
