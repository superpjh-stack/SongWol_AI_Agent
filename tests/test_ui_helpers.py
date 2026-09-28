from songwol_agent import QUESTION_GROUPS, SongwolRepository, lot_snapshot, risk_label, user_question_history

def test_cockpit_helpers(tmp_path):
    repo=SongwolRepository(tmp_path/"demo.db")
    snap=lot_snapshot(repo,"PRT-260903-C")
    assert snap["quality"][0]["result"]=="보류"
    assert risk_label(snap)==("높음","🔴")
    assert "LOT·품질" in QUESTION_GROUPS
    assert user_question_history([{"role":"user","content":"품질","created_at":"10:00"}])[0]["content"]=="품질"
