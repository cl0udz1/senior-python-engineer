class RetryableConflict(Exception): pass
def run_transaction(connect, work, max_attempts=3):
    connection=connect()
    for attempt in range(max_attempts):
        try:
            result=work(connection);connection.commit();return result
        except RetryableConflict:
            if attempt+1==max_attempts:raise
    connection.close()
